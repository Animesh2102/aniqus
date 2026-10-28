import time
from typing import List, Dict, Any, AsyncGenerator, Tuple
from app.core.config import settings
from app.core.security import get_allowed_access_levels
from app.services.vector_store import VectorStoreService
from app.services.bm25 import BM25Service
from app.services.reranker import RerankerService
from app.services.cache import SemanticCacheService
from app.services.llm import LLMService

class RAGService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.vector_store = VectorStoreService.get_instance()
        self.bm25_service = BM25Service.get_instance()
        self.reranker_service = RerankerService.get_instance()
        self.cache_service = SemanticCacheService.get_instance()
        self.llm_service = LLMService.get_instance()
        
        # Warm up BM25 index from vector store chunks
        self.refresh_bm25()

    def refresh_bm25(self):
        chunks = self.vector_store.get_all_chunks()
        self.bm25_service.update_index(chunks)

    def hybrid_search(
        self,
        query: str,
        user_role: str,
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        allowed_access = get_allowed_access_levels(user_role)
        
        dense_results = self.vector_store.search_dense(
            query=query,
            allowed_access_levels=allowed_access,
            top_k=top_k
        )
        
        sparse_results = self.bm25_service.search_sparse(
            query=query,
            allowed_access_levels=allowed_access,
            top_k=top_k
        )
        
        # Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}
        chunks_map: Dict[str, Dict[str, Any]] = {}
        
        for rank, item in enumerate(dense_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (settings.RRF_K + rank + 1))
            chunks_map[cid] = item
            
        for rank, item in enumerate(sparse_results):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (settings.RRF_K + rank + 1))
            if cid not in chunks_map:
                chunks_map[cid] = item

        # Sort combined results by RRF score
        fused = []
        for cid, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            entry = dict(chunks_map[cid])
            entry["rrf_score"] = score
            fused.append(entry)
            
        return fused[:top_k]

    async def execute_query(
        self,
        query: str,
        user_role: str = "engineering"
    ) -> Tuple[bool, List[Dict[str, Any]], Dict[str, float], AsyncGenerator[str, None]]:
        """
        Executes end-to-end RAG pipeline:
        Returns: (is_cached, citations, latency_breakdown, answer_stream)
        """
        latencies = {}
        t0 = time.time()
        
        # 1. Semantic Cache check
        cached_result = self.cache_service.lookup(query, user_role)
        latencies["cache_lookup_ms"] = round((time.time() - t0) * 1000, 2)
        
        if cached_result:
            async def cached_stream():
                for word in cached_result["answer"].split(" "):
                    yield word + " "
            latencies["total_latency_ms"] = latencies["cache_lookup_ms"]
            return True, cached_result["citations"], latencies, cached_stream()

        # 2. Hybrid Retrieval (Dense + BM25 + ACL)
        t_ret = time.time()
        fused_candidates = self.hybrid_search(query, user_role, top_k=settings.HYBRID_SEARCH_TOP_K)
        latencies["retrieval_ms"] = round((time.time() - t_ret) * 1000, 2)

        # 3. Cross-Encoder Re-ranking
        t_rerank = time.time()
        raw_passages = self.reranker_service.rerank(
            query=query,
            candidates=fused_candidates,
            top_k=settings.RERANK_TOP_K
        )
        latencies["rerank_ms"] = round((time.time() - t_rerank) * 1000, 2)

        # Confidence thresholding: discard chunks if cross-encoder relevance is low (prevents hallucination on out-of-domain or unauthorized queries)
        top_passages = [p for p in raw_passages if p.get("rerank_score", 0.0) >= 0.005]

        # Build clean citations list for UI cards
        citations = []
        for p in top_passages:
            citations.append({
                "chunk_id": p.get("chunk_id"),
                "filename": p.get("filename"),
                "page_number": p.get("page_number", 1),
                "section_title": p.get("section_title", "General"),
                "access_level": p.get("access_level", "all"),
                "department": p.get("department", "general"),
                "snippet": p.get("content", "")[:180] + "...",
                "rerank_score": p.get("rerank_score", 0.0)
            })

        # 4. Streamed Grounded Answer
        full_answer_accumulator = []
        async def response_stream():
            t_gen_start = time.time()
            async for token in self.llm_service.stream_answer(query, top_passages):
                full_answer_accumulator.append(token)
                yield token
            
            # Store in semantic cache on completion if meaningful
            full_text = "".join(full_answer_accumulator).strip()
            if top_passages and len(full_text) > 20:
                self.cache_service.store(query, user_role, full_text, citations)

        return False, citations, latencies, response_stream()
