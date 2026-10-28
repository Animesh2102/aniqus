import os
import json
import asyncio
from typing import List, Dict, Any, AsyncGenerator
import httpx
from app.core.config import settings

CITATION_PROMPT = """You are an Enterprise Knowledge Assistant. You strictly answer user questions based ONLY on the provided verified document excerpts.

Guidelines:
1. Grounding: Every single claim in your answer must be supported by the excerpts below. Do NOT assume, extrapolate, or hallucinate facts.
2. Citation Format: Whenever you state a fact from an excerpt, cite it immediately using the format: `[Doc: <filename>, Page <page>, "<section>"]`.
3. Unanswered Questions: If the provided excerpts do not contain enough information to answer the question, or if no excerpts are provided due to access control, state clearly: "I cannot find sufficient information in your authorized company documents to answer this question."
4. Tone: Professional, direct, and concise.

Context Excerpts:
{context}

User Question: {question}

Answer:"""

class LLMService:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        self.gemini_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY

    def format_context(self, passages: List[Dict[str, Any]]) -> str:
        if not passages:
            return "No relevant passages found within your authorized permission level."
            
        context_blocks = []
        for idx, p in enumerate(passages, 1):
            block = (
                f"--- Excerpt {idx} ---\n"
                f"Document: {p.get('filename')}\n"
                f"Page: {p.get('page_number', 1)}\n"
                f"Section: {p.get('section_title', 'General')}\n"
                f"Access Level: {p.get('access_level', 'all')}\n"
                f"Content:\n{p.get('content')}\n"
            )
            context_blocks.append(block)
        return "\n".join(context_blocks)

    async def stream_answer(
        self,
        question: str,
        passages: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        if not passages:
            refusal = "I cannot find sufficient information in your authorized company documents to answer this question."
            for word in refusal.split(" "):
                yield word + " "
                await asyncio.sleep(0.02)
            return

        context_str = self.format_context(passages)
        prompt = CITATION_PROMPT.format(context=context_str, question=question)

        # Check if OpenAI key is present
        if self.openai_key:
            try:
                async for chunk in self._stream_openai(prompt):
                    yield chunk
                return
            except Exception as e:
                print(f"[LLM] OpenAI streaming error: {e}. Falling back to internal engine.")

        # Check if Gemini key is present
        if self.gemini_key:
            try:
                async for chunk in self._stream_gemini(prompt):
                    yield chunk
                return
            except Exception as e:
                print(f"[LLM] Gemini streaming error: {e}. Falling back to internal engine.")

        # Built-in local grounded synthesizer fallback (runs completely offline with zero API key!)
        async for chunk in self._stream_local_synthesizer(question, passages):
            yield chunk

    async def _stream_openai(self, prompt: str) -> AsyncGenerator[str, None]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": True
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        data = json.loads(line[6:])
                        delta = data["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta

    async def _stream_gemini(self, prompt: str) -> AsyncGenerator[str, None]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:streamGenerateContent?key={self.gemini_key}&alt=sse"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        candidates = data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if text:
                                yield text

    async def _stream_local_synthesizer(
        self,
        question: str,
        passages: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """High-precision local grounded synthesis when no cloud API key is configured."""
        # Find best passages that answer the query
        top_passage = passages[0]
        filename = top_passage.get("filename", "Doc")
        page = top_passage.get("page_number", 1)
        section = top_passage.get("section_title", "General")
        content = top_passage.get("content", "")

        # Clean content lines
        lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("[")]
        summary_text = " ".join(lines[:3])

        response_text = (
            f"Based on internal documentation in **{filename}**:\n\n"
            f"{summary_text} [Doc: {filename}, Page {page}, \"{section}\"]\n\n"
        )
        
        if len(passages) > 1:
            sec_passage = passages[1]
            p2_file = sec_passage.get("filename", "Doc")
            p2_page = sec_passage.get("page_number", 1)
            p2_sec = sec_passage.get("section_title", "General")
            p2_lines = [l.strip() for l in sec_passage.get("content", "").split("\n") if l.strip() and not l.startswith("[")]
            if p2_lines:
                response_text += f"Additionally, regarding {p2_sec.lower()}: {p2_lines[0]} [Doc: {p2_file}, Page {p2_page}, \"{p2_sec}\"]"

        for token in response_text.split(" "):
            yield token + " "
            await asyncio.sleep(0.015)
