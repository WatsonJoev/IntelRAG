"""HTML parser: extracts clean text via BeautifulSoup4."""
from __future__ import annotations

from bs4 import BeautifulSoup

from ingestion.parsers.base import BaseParser, ParsedDocument


class HTMLParser(BaseParser):
    supported_extensions = [".html", ".htm"]
    supported_mime_types = ["text/html"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else ""
        return ParsedDocument(
            text=text,
            page_count=1,
            title=title or "",
            metadata={"filename": filename},
        )
