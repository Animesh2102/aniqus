from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import init_db
from app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise RAG Assistant with Hybrid Search (BM25 + Dense Vectors), Cross-Encoder Re-ranking, Document ACLs, Semantic Caching, and Continuous Evaluations.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "reranker_model": settings.RERANKER_MODEL_NAME
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
