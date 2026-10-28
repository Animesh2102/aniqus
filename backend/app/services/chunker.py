import uuid
import re
from typing import List, Dict, Any

class DocumentChunker:
    """Structure-aware chunker that preserves section headers, page numbers, and ACL tags."""
    
    def __init__(self, target_chunk_size: int = 500, chunk_overlap: int = 100):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        doc_id: str,
        filename: str,
        department: str,
        access_level: str,
        sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        chunks = []
        chunk_idx = 0

        for section in sections:
            section_title = section.get("section_title", "General")
            page_number = section.get("page_number", 1)
            raw_text = section.get("text", "")
            
            # Split section by paragraphs or double newlines
            paragraphs = re.split(r'\n{2,}', raw_text)
            current_chunk = f"[{section_title}]\n" if section_title != "General" else ""
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                    
                if len(current_chunk) + len(para) <= self.target_chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    if len(current_chunk.strip()) > 30:
                        chunks.append({
                            "chunk_id": f"{doc_id}-c{chunk_idx}",
                            "doc_id": doc_id,
                            "filename": filename,
                            "department": department,
                            "access_level": access_level,
                            "page_number": page_number,
                            "section_title": section_title,
                            "content": current_chunk.strip()
                        })
                        chunk_idx += 1
                    
                    # Start new chunk with overlap if possible
                    if len(para) > self.target_chunk_size:
                        # Break large paragraph by sentences
                        sentences = re.split(r'(?<=[.!?])\s+', para)
                        current_chunk = f"[{section_title}]\n" if section_title != "General" else ""
                        for sent in sentences:
                            if len(current_chunk) + len(sent) <= self.target_chunk_size:
                                current_chunk += sent + " "
                            else:
                                if len(current_chunk.strip()) > 30:
                                    chunks.append({
                                        "chunk_id": f"{doc_id}-c{chunk_idx}",
                                        "doc_id": doc_id,
                                        "filename": filename,
                                        "department": department,
                                        "access_level": access_level,
                                        "page_number": page_number,
                                        "section_title": section_title,
                                        "content": current_chunk.strip()
                                    })
                                    chunk_idx += 1
                                current_chunk = sent + " "
                    else:
                        current_chunk = para + "\n\n"

            if len(current_chunk.strip()) > 30:
                chunks.append({
                    "chunk_id": f"{doc_id}-c{chunk_idx}",
                    "doc_id": doc_id,
                    "filename": filename,
                    "department": department,
                    "access_level": access_level,
                    "page_number": page_number,
                    "section_title": section_title,
                    "content": current_chunk.strip()
                })
                chunk_idx += 1

        return chunks
