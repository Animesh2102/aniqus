import os
from typing import List
from fastembed import TextEmbedding
from app.core.config import settings

class EmbeddingService:
    """Provides high-speed local dense embeddings using FastEmbed (BGE-small)."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Initialize FastEmbed with BAAI/bge-small-en-v1.5 (384-dimensional)
        self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
        self.dimension = 384

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings_generator = self.model.embed(texts)
        return [emb.tolist() for emb in embeddings_generator]

    def embed_query(self, query: str) -> List[float]:
        # FastEmbed optimizes passage vs query representation
        return self.embed_texts([f"Represent this sentence for searching relevant passages: {query}"])[0]
