"""JSON and XML parser: flattens nested structures to text."""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from ingestion.parsers.base import BaseParser, ParsedDocument


def _flatten_json(obj: object, parts: list) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _flatten_json(v, parts)
    elif isinstance(obj, list):
        for item in obj:
            _flatten_json(item, parts)
    elif obj is not None:
        parts.append(str(obj))


def _flatten_xml(element: ElementTree.Element, parts: list) -> None:
    if element.text and element.text.strip():
        parts.append(element.text.strip())
    for child in element:
        _flatten_xml(child, parts)
    if element.tail and element.tail.strip():
        parts.append(element.tail.strip())


class JSONXMLParser(BaseParser):
    supported_extensions = [".json", ".xml"]
    supported_mime_types = ["application/json", "application/xml", "text/xml"]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        ext = Path(filename).suffix.lower()
        parts: list = []
        if ext == ".json":
            data = json.loads(content.decode("utf-8", errors="replace"))
            _flatten_json(data, parts)
        else:
            root = ElementTree.fromstring(content.decode("utf-8", errors="replace"))
            _flatten_xml(root, parts)
        text = "\n".join(parts)
        return ParsedDocument(
            text=text,
            page_count=1,
            metadata={"filename": filename},
        )
