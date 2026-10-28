import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader

class DocumentParser:
    """Extracts raw text, page numbers, and structural section headers from documents."""
    
    @staticmethod
    def parse_file(file_path: str) -> List[Dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return DocumentParser._parse_pdf(file_path)
        elif ext in [".md", ".markdown"]:
            return DocumentParser._parse_markdown(file_path)
        else:
            return DocumentParser._parse_text(file_path)
            
    @staticmethod
    def _parse_pdf(file_path: str) -> List[Dict[str, Any]]:
        pages_content = []
        reader = PdfReader(file_path)
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages_content.append({
                    "page_number": idx + 1,
                    "section_title": f"Page {idx + 1}",
                    "text": text
                })
        return pages_content

    @staticmethod
    def _parse_markdown(file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split markdown into sections by headers (#, ##, ###)
        header_pattern = re.compile(r'^(#{1,3}\s+.+)$', re.MULTILINE)
        splits = header_pattern.split(content)
        
        sections = []
        current_title = "Document Overview"
        
        # If there's content before the first header
        if splits and not header_pattern.match(splits[0]):
            init_text = splits[0].strip()
            if init_text:
                sections.append({
                    "page_number": 1,
                    "section_title": current_title,
                    "text": init_text
                })
            splits = splits[1:]
            
        for i in range(0, len(splits), 2):
            if i + 1 < len(splits):
                title = splits[i].strip("# ").strip()
                text = splits[i+1].strip()
                if text:
                    sections.append({
                        "page_number": 1,
                        "section_title": title,
                        "text": text
                    })
        if not sections and content.strip():
            sections.append({
                "page_number": 1,
                "section_title": "Overview",
                "text": content.strip()
            })
        return sections

    @staticmethod
    def _parse_text(file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return [{
            "page_number": 1,
            "section_title": "General",
            "text": content
        }]
