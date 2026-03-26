"""
Parser factory: auto-detect file type (mimetypes) and route to correct parser.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from config.logging_config import get_logger

if TYPE_CHECKING:
    from ingestion.parsers.base import BaseParser

logger = get_logger(__name__)

# Lazy imports to avoid loading heavy libs until needed
_parsers: dict[str, type[BaseParser]] = {}


def _get_parsers() -> dict[str, type[BaseParser]]:
    global _parsers
    if not _parsers:
        from ingestion.parsers.pdf_parser import PDFParser
        from ingestion.parsers.docx_parser import DOCXParser
        from ingestion.parsers.txt_parser import TXTParser
        from ingestion.parsers.csv_parser import CSVParser
        from ingestion.parsers.pptx_parser import PPTXParser
        from ingestion.parsers.html_parser import HTMLParser
        from ingestion.parsers.json_xml_parser import JSONXMLParser

        for cls in (PDFParser, DOCXParser, TXTParser, CSVParser, PPTXParser, HTMLParser, JSONXMLParser):
            p = cls()
            for ext in p.supported_extensions:
                _parsers[ext.lower()] = cls
            for mime in p.supported_mime_types:
                _parsers[mime.lower()] = cls
    return _parsers


def get_parser_for_filename(filename: str) -> type[BaseParser] | None:
    """Return parser class for filename (extension-based)."""
    ext = Path(filename).suffix.lower()
    if not ext:
        return None
    parsers = _get_parsers()
    return parsers.get(ext)


def get_parser_for_content(content: bytes, filename: str) -> BaseParser | None:
    """
    Detect parser by extension first, then by mimetype if available.
    Returns parser instance or None if unsupported.
    """
    cls = get_parser_for_filename(filename)
    if cls:
        return cls()
    guess, _ = mimetypes.guess_type(filename)
    if guess:
        parsers = _get_parsers()
        cls = parsers.get(guess.lower())
        if cls:
            return cls()
    logger.warning("no_parser_found", filename=filename)
    return None
