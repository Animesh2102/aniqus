import time
import numpy as np
from typing import Optional, Dict, Any, List
from app.services.embeddings import EmbeddingService
from app.core.config import settings

class SemanticCacheService:
    """In-memory vector semantic cache to return instant answers for semantically identical questions."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.embedding_service = EmbeddingService.get_instance()
        # List of dicts: {"query": str, "vector": np.ndarray, "role": str, "answer": str, "citations": list, "timestamp": float}
        self.cache: List[Dict[str, Any]] = []

    def lookup(self, query: str, user_role: str) -> Optional[Dict[str, Any]]:
        if not self.cache:
            return None
            
        query_vec = np.array(self.embedding_service.embed_query(query))
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return None
            
        best_match = None
        best_sim = -1.0
        
        for item in self.cache:
            # Must match the same role context for security
            if item["role"] != user_role:
                continue
                
            item_vec = item["vector"]
            sim = np.dot(query_vec, item_vec) / (query_norm * np.linalg.norm(item_vec))
            if sim > best_sim:
                best_sim = float(sim)
                best_match = item
                
        if best_sim >= settings.SEMANTIC_CACHE_THRESHOLD and best_match:
            return {
                "answer": best_match["answer"],
                "citations": best_match["citations"],
                "similarity": best_sim,
                "cached_query": best_match["query"]
            }
        return None

    def store(self, query: str, user_role: str, answer: str, citations: List[Dict[str, Any]]):
        query_vec = np.array(self.embedding_service.embed_query(query))
        self.cache.append({
            "query": query,
            "vector": query_vec,
            "role": user_role,
            "answer": answer,
            "citations": citations,
            "timestamp": time.time()
        })
        # Keep cache capped to last 1000 items
        if len(self.cache) > 1000:
            self.cache.pop(0)

    def clear(self):
        self.cache.clear()
