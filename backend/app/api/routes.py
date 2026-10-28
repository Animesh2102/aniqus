import os
import shutil
import uuid
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ROLE_PERMISSIONS, get_allowed_access_levels
from app.db.database import get_db, DocumentModel, ChatMessageModel, EvaluationRecordModel, AsyncSessionLocal
from app.services.parser import DocumentParser
from app.services.chunker import DocumentChunker
from app.services.vector_store import VectorStoreService
from app.services.rag_service import RAGService
from app.services.evaluator import EvaluationService

router = APIRouter()
chunker = DocumentChunker()
vector_store = VectorStoreService.get_instance()
rag_service = RAGService.get_instance()
eval_service = EvaluationService()

# ----------------- Models -----------------
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_role: str = "engineering"

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int # 1 or -1
    comment: Optional[str] = None

# ----------------- Health -----------------
@router.get("/health")
async def api_health():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "reranker_model": settings.RERANKER_MODEL_NAME
    }

# ----------------- Roles & ACL -----------------
@router.get("/roles")
async def list_roles():
    return {
        "roles": list(ROLE_PERMISSIONS.keys()),
        "permissions_matrix": ROLE_PERMISSIONS
    }

# ----------------- Document Management -----------------
@router.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentModel).order_by(DocumentModel.created_at.desc()))
    docs = result.scalars().all()
    return [{
        "id": d.id,
        "filename": d.filename,
        "file_type": d.file_type,
        "file_size": d.file_size,
        "department": d.department,
        "access_level": d.access_level,
        "chunk_count": d.chunk_count,
        "created_at": d.created_at.isoformat() if d.created_at else None
    } for d in docs]

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form("engineering"),
    access_level: str = Form("engineering"),
    db: AsyncSession = Depends(get_db)
):
    doc_id = str(uuid.uuid4())
    safe_filename = file.filename
    save_path = os.path.join(settings.DOCS_DIR, f"{doc_id}_{safe_filename}")
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(save_path)
    file_type = os.path.splitext(safe_filename)[1].lstrip(".").lower()
    
    # Parse & Chunk
    parsed_sections = DocumentParser.parse_file(save_path)
    chunks = chunker.chunk_document(
        doc_id=doc_id,
        filename=safe_filename,
        department=department,
        access_level=access_level,
        sections=parsed_sections
    )
    
    # Upsert to Vector Store & refresh BM25
    vector_store.upsert_chunks(chunks)
    rag_service.refresh_bm25()
    
    # Save to SQLite
    doc_record = DocumentModel(
        id=doc_id,
        filename=safe_filename,
        file_path=save_path,
        file_type=file_type,
        file_size=file_size,
        department=department,
        access_level=access_level,
        chunk_count=len(chunks)
    )
    db.add(doc_record)
    await db.commit()
    
    return {
        "status": "success",
        "doc_id": doc_id,
        "filename": safe_filename,
        "chunk_count": len(chunks),
        "access_level": access_level
    }

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Delete from Qdrant
    vector_store.delete_document(doc_id)
    rag_service.refresh_bm25()
    
    # Remove physical file if exists
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass
            
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "doc_id": doc_id}

@router.post("/documents/seed")
async def seed_sample_documents(db: AsyncSession = Depends(get_db)):
    """Seed the 4 standard enterprise test documents into the knowledge base."""
    sample_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "sample_docs"
    )
    
    meta_map = {
        "engineering_sop_deployment.md": ("engineering", "engineering"),
        "hr_compensation_and_equity_policy.md": ("hr", "hr"),
        "company_travel_and_expenses_handbook.md": ("finance", "all"),
        "information_security_incident_response.md": ("security", "engineering")
    }
    
    seeded = []
    if not os.path.exists(sample_dir):
        return {"status": "error", "message": "sample_docs folder not found"}
        
    for fname, (dept, acl) in meta_map.items():
        src_path = os.path.join(sample_dir, fname)
        if not os.path.exists(src_path):
            continue
            
        doc_id = f"seed-{fname.replace('.', '-').replace('_', '-')}"
        dest_path = os.path.join(settings.DOCS_DIR, f"{doc_id}_{fname}")
        shutil.copy2(src_path, dest_path)
        
        parsed_sections = DocumentParser.parse_file(dest_path)
        chunks = chunker.chunk_document(
            doc_id=doc_id,
            filename=fname,
            department=dept,
            access_level=acl,
            sections=parsed_sections
        )
        
        vector_store.upsert_chunks(chunks)
        
        # Check if already in DB
        res = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        existing = res.scalar_one_or_none()
        if existing:
            existing.chunk_count = len(chunks)
            existing.indexed_at = datetime.utcnow()
        else:
            doc_record = DocumentModel(
                id=doc_id,
                filename=fname,
                file_path=dest_path,
                file_type="markdown",
                file_size=os.path.getsize(dest_path),
                department=dept,
                access_level=acl,
                chunk_count=len(chunks)
            )
            db.add(doc_record)
        seeded.append(fname)
        
    await db.commit()
    rag_service.refresh_bm25()
    return {"status": "seeded", "documents": seeded}

# ----------------- RAG Chat & Streaming -----------------
@router.post("/chat/stream")
async def chat_stream(req: QueryRequest, db: AsyncSession = Depends(get_db)):
    session_id = req.session_id or str(uuid.uuid4())
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())
    
    # Save user message to database
    user_msg = ChatMessageModel(
        id=user_msg_id,
        session_id=session_id,
        role="user",
        user_role=req.user_role,
        content=req.query
    )
    db.add(user_msg)
    await db.commit()
    
    is_cached, citations, latencies, token_stream = await rag_service.execute_query(
        query=req.query,
        user_role=req.user_role
    )
    
    async def sse_generator():
        # First send citation metadata & latency metrics
        init_event = {
            "type": "meta",
            "message_id": assistant_msg_id,
            "session_id": session_id,
            "cached_hit": is_cached,
            "citations": citations,
            "latencies": latencies
        }
        yield f"data: {json.dumps(init_event)}\n\n"
        
        full_tokens = []
        async for token in token_stream:
            full_tokens.append(token)
            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
            
        full_answer = "".join(full_tokens)
        
        # Save assistant message to DB
        try:
            async with AsyncSessionLocal() as local_db:
                assistant_msg = ChatMessageModel(
                    id=assistant_msg_id,
                    session_id=session_id,
                    role="assistant",
                    user_role=req.user_role,
                    content=full_answer,
                    citations=citations,
                    latency_breakdown=latencies,
                    cached_hit=is_cached
                )
                local_db.add(assistant_msg)
                await local_db.commit()
        except Exception as err:
            print(f"[ChatStream] DB save error: {err}")

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session_id)
        .order_by(ChatMessageModel.created_at.asc())
    )
    messages = result.scalars().all()
    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "citations": m.citations,
        "latency_breakdown": m.latency_breakdown,
        "cached_hit": m.cached_hit,
        "feedback_rating": m.feedback_rating,
        "created_at": m.created_at.isoformat() if m.created_at else None
    } for m in messages]

@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatMessageModel).where(ChatMessageModel.id == req.message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    msg.feedback_rating = req.rating
    msg.feedback_comment = req.comment
    await db.commit()
    return {"status": "recorded"}

# ----------------- Evaluations & Benchmarks -----------------
@router.post("/evaluations/run")
async def run_evaluation():
    """Runs the 10-query benchmark dataset and calculates faithfulness, precision, and ACL compliance."""
    report = await eval_service.run_benchmark()
    return report

@router.get("/evaluations/history")
async def list_evaluations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationRecordModel).order_by(EvaluationRecordModel.run_timestamp.desc()).limit(10)
    )
    records = result.scalars().all()
    return [{
        "id": r.id,
        "run_timestamp": r.run_timestamp.isoformat() if r.run_timestamp else None,
        "total_samples": r.total_samples,
        "faithfulness_score": r.faithfulness_score,
        "context_precision": r.context_precision,
        "acl_compliance_rate": r.acl_compliance_rate,
        "avg_latency_ms": r.avg_latency_ms,
        "detailed_results": r.detailed_results
    } for r in records]
