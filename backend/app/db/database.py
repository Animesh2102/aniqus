import os
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.config import settings

Base = declarative_base()

class DocumentModel(Base):
    __tablename__ = "documents"
    
    id = Column(String(64), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(32), nullable=False) # 'pdf', 'markdown', 'text'
    file_size = Column(Integer, default=0)
    department = Column(String(64), default="general")
    access_level = Column(String(64), default="all") # 'all', 'engineering', 'hr', 'executive'
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime, default=datetime.utcnow)

class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(16), nullable=False) # 'user', 'assistant'
    user_role = Column(String(32), default="engineering") # role of caller
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    latency_breakdown = Column(JSON, default=dict)
    cached_hit = Column(Boolean, default=False)
    feedback_rating = Column(Integer, nullable=True) # 1 (up) or -1 (down)
    feedback_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class EvaluationRecordModel(Base):
    __tablename__ = "evaluation_records"
    
    id = Column(String(64), primary_key=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    total_samples = Column(Integer, default=0)
    faithfulness_score = Column(Float, default=0.0)
    relevancy_score = Column(Float, default=0.0)
    context_precision = Column(Float, default=0.0)
    acl_compliance_rate = Column(Float, default=1.0)
    avg_latency_ms = Column(Float, default=0.0)
    detailed_results = Column(JSON, default=list)

DATABASE_URL = f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
