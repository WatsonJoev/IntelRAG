"""TXT and Markdown parser."""
from __future__ import annotations

from ingestion.parsers.base import BaseParser, ParsedDocument


class TXTParser(BaseParser):
    supported_extensions = [".txt", ".md", ".markdown"]
    supported_mime_types = ["text/plain", "text/markdown"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        return ParsedDocument(
            text=text.strip(),
            metadata={},
            page_count=1,
            title=filename,
        )
