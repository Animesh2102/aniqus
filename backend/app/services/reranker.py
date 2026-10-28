from typing import List, Dict, Any
from flashrank import Ranker, RerankRequest
from app.core.config import settings

class RerankerService:
    """Provides fast local Cross-Encoder re-ranking using FlashRank."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Uses lightweight ms-marco-TinyBERT-L-2-v2 (approx 4MB model, < 15ms latency)
        self.ranker = Ranker(model_name=settings.RERANKER_MODEL_NAME, cache_dir="./data/cache")

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 4) -> List[Dict[str, Any]]:
        if not candidates:
            return []
            
        passages = [
            {"id": i, "text": c["content"], "meta": c}
            for i, c in enumerate(candidates)
        ]
        
        rerank_req = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(rerank_req)
        
        reranked = []
        for r in results[:top_k]:
            meta = dict(r["meta"])
            meta["rerank_score"] = float(r["score"])
            reranked.append(meta)
            
        return reranked
