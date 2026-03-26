"""PDF parser using PyMuPDF (fitz)."""
from __future__ import annotations

import fitz  # PyMuPDF

from ingestion.parsers.base import BaseParser, ParsedDocument


class PDFParser(BaseParser):
    supported_extensions = [".pdf"]
    supported_mime_types = ["application/pdf"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            texts = []
            for i in range(len(doc)):
                page = doc[i]
                texts.append(page.get_text())
            text = "\n\n".join(texts)
            meta = doc.metadata or {}
            title = (meta.get("title") or filename) or ""
            return ParsedDocument(
                text=text.strip(),
                metadata={
                    "author": meta.get("author"),
                    "subject": meta.get("subject"),
                    "creator": meta.get("creator"),
                    "producer": meta.get("producer"),
                },
                page_count=len(doc),
                title=title,
            )
        finally:
            doc.close()
