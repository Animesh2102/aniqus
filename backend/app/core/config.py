import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Aniqus — Enterprise Knowledge Engine"
    API_V1_STR: str = "/api"
    
    # Storage paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    QDRANT_PATH: str = os.path.join(BASE_DIR, "data", "qdrant_db")
    SQLITE_PATH: str = os.path.join(BASE_DIR, "data", "enterprise_rag.db")
    DOCS_DIR: str = os.path.join(BASE_DIR, "data", "documents")
    
    # Models & Embeddings
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL_NAME: str = "ms-marco-TinyBERT-L-2-v2"
    
    # Retrieval Tuning
    HYBRID_SEARCH_TOP_K: int = 15
    RERANK_TOP_K: int = 4
    RRF_K: int = 60
    SEMANTIC_CACHE_THRESHOLD: float = 0.94
    
    # LLM Settings (supports OpenAI, Gemini, Ollama, or local fallback)
    LLM_PROVIDER: str = "auto" # 'openai', 'gemini', 'ollama', or 'auto'
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.DOCS_DIR, exist_ok=True)
