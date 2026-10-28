import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List
from app.services.rag_service import RAGService
from app.core.security import is_role_permitted
from app.db.database import AsyncSessionLocal, EvaluationRecordModel

class EvaluationService:
    """Automated benchmark evaluator measuring faithfulness, relevancy, ACL compliance, and latency."""
    
    def __init__(self):
        self.rag_service = RAGService.get_instance()

    async def run_benchmark(self, dataset_path: str = None) -> Dict[str, Any]:
        if not dataset_path:
            dataset_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "eval_data",
                "benchmark_dataset.json"
            )
            
        with open(dataset_path, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

        results = []
        total_faithfulness = 0.0
        total_precision = 0.0
        acl_violations = 0
        total_latency = 0.0
        
        for case in test_cases:
            qid = case["id"]
            question = case["question"]
            target_doc = case.get("target_doc")
            required_acl = case.get("required_acl", "all")
            forbidden_roles = case.get("forbidden_roles", [])
            expected_action = case.get("expected_action", "answer")

            # 1. Test Authorized Query Execution
            test_role = "executive" if required_acl == "executive" else ("hr" if required_acl == "hr" else "engineering")
            
            t0 = time.time()
            is_cached, citations, latencies, stream = await self.rag_service.execute_query(
                query=question,
                user_role=test_role
            )
            answer_tokens = [tok async for tok in stream]
            full_answer = "".join(answer_tokens)
            elapsed_ms = (time.time() - t0) * 1000
            total_latency += elapsed_ms

            # Metric: Context Precision (Did we retrieve the target document?)
            retrieved_files = [c["filename"] for c in citations]
            if target_doc:
                target_hit = 1.0 if any(target_doc in rf for rf in retrieved_files) else 0.0
            else:
                target_hit = 1.0 if len(citations) == 0 or "cannot find" in full_answer.lower() else 0.5
            total_precision += target_hit

            # Metric: Faithfulness (Check overlap of content tokens between context and answer)
            combined_context = " ".join([c["snippet"] for c in citations]).lower()
            answer_words = [w.strip(".,;:?!()[]\"") for w in full_answer.lower().split() if len(w) > 3]
            if answer_words:
                supported_words = sum(1 for w in answer_words if w in combined_context or w in question.lower())
                faithfulness = round(supported_words / len(answer_words), 2)
            else:
                faithfulness = 1.0
            total_faithfulness += faithfulness

            # 2. Test Forbidden Role Query (Security / ACL Test)
            acl_passed = True
            for f_role in forbidden_roles:
                _, f_citations, _, _ = await self.rag_service.execute_query(
                    query=question,
                    user_role=f_role
                )
                # Check if any forbidden documents were leaked
                for f_cit in f_citations:
                    if f_cit.get("access_level") not in ["all", f_role]:
                        acl_violations += 1
                        acl_passed = False
                        break

            results.append({
                "id": qid,
                "question": question,
                "target_doc": target_doc,
                "test_role": test_role,
                "target_hit": target_hit,
                "faithfulness": faithfulness,
                "latency_ms": round(elapsed_ms, 1),
                "acl_check_passed": acl_passed,
                "answer_preview": full_answer[:120] + "..." if len(full_answer) > 120 else full_answer
            })

        n = len(test_cases)
        avg_faithfulness = round((total_faithfulness / n) * 100, 1)
        avg_precision = round((total_precision / n) * 100, 1)
        acl_compliance = round(((n - acl_violations) / n) * 100, 1)
        avg_latency = round(total_latency / n, 1)

        summary = {
            "id": str(uuid.uuid4()),
            "run_timestamp": datetime.utcnow().isoformat(),
            "total_samples": n,
            "faithfulness_score": avg_faithfulness,
            "context_precision": avg_precision,
            "acl_compliance_rate": acl_compliance,
            "avg_latency_ms": avg_latency,
            "detailed_results": results
        }

        # Store in DB
        async with AsyncSessionLocal() as session:
            record = EvaluationRecordModel(
                id=summary["id"],
                total_samples=summary["total_samples"],
                faithfulness_score=summary["faithfulness_score"],
                relevancy_score=summary["context_precision"],
                context_precision=summary["context_precision"],
                acl_compliance_rate=summary["acl_compliance_rate"],
                avg_latency_ms=summary["avg_latency_ms"],
                detailed_results=summary["detailed_results"]
            )
            session.add(record)
            await session.commit()

        return summary
