import re
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi

class BM25Service:
    """Maintains an in-memory BM25 index with tokenization and ACL filtering."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: BM25Okapi = None

    def tokenize(self, text: str) -> List[str]:
        # Lowercase, alphanumeric tokenization
        return re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', text.lower())

    def update_index(self, all_chunks: List[Dict[str, Any]]):
        self.chunks = all_chunks
        if not self.chunks:
            self.bm25 = None
            return
        corpus = [self.tokenize(c["content"]) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus)

    def search_sparse(
        self,
        query: str,
        allowed_access_levels: List[str],
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.chunks:
            return []
            
        tokens = self.tokenize(query)
        if not tokens:
            return []
            
        scores = self.bm25.get_scores(tokens)
        
        # Filter by ACL and associate scores
        scored_candidates = []
        for idx, score in enumerate(scores):
            chunk = self.chunks[idx]
            if chunk.get("access_level") in allowed_access_levels and score > 0.0:
                scored_chunk = dict(chunk)
                scored_chunk["sparse_score"] = float(score)
                scored_candidates.append(scored_chunk)
                
        # Sort by sparse_score descending
        scored_candidates.sort(key=lambda x: x["sparse_score"], reverse=True)
        return scored_candidates[:top_k]
