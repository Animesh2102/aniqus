import os
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from app.core.config import settings
from app.services.embeddings import EmbeddingService

COLLECTION_NAME = "enterprise_documents"

class VectorStoreService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.embedding_service = EmbeddingService.get_instance()
        os.makedirs(settings.QDRANT_PATH, exist_ok=True)
        self.client = QdrantClient(path=settings.QDRANT_PATH)
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=rest.VectorParams(
                    size=self.embedding_service.dimension,
                    distance=rest.Distance.COSINE
                )
            )
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="access_level",
                    field_schema=rest.PayloadSchemaType.KEYWORD
                )
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="doc_id",
                    field_schema=rest.PayloadSchemaType.KEYWORD
                )
            except Exception:
                pass

    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        if not chunks:
            return 0
            
        texts = [c["content"] for c in chunks]
        embeddings = self.embedding_service.embed_texts(texts)
        
        points = []
        for i, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"]))
            points.append(
                rest.PointStruct(
                    id=point_id,
                    vector=embeddings[i],
                    payload=chunk
                )
            )
            
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        return len(points)

    def search_dense(
        self,
        query: str,
        allowed_access_levels: List[str],
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        query_vector = self.embedding_service.embed_query(query)
        
        # Build ACL filter
        acl_filter = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="access_level",
                    match=rest.MatchAny(any=allowed_access_levels)
                )
            ]
        )
        
        # Query Qdrant with ACL payload filter
        if hasattr(self.client, "query_points"):
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=acl_filter,
                limit=top_k,
                with_payload=True
            ).points
        else:
            results = self.client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=acl_filter,
                limit=top_k
            )
        
        formatted = []
        for hit in results:
            payload = dict(hit.payload)
            payload["dense_score"] = float(hit.score)
            formatted.append(payload)
        return formatted

    def delete_document(self, doc_id: str):
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="doc_id",
                            match=rest.MatchValue(value=doc_id)
                        )
                    ]
                )
            )
        )

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        # Scroll through all points for BM25 indexing
        records, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        return [r.payload for r in records if r.payload]
