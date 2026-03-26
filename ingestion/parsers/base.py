"""Base parser interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedDocument:
    """Result of parsing a document."""

    text: str
    metadata: dict[str, Any]
    page_count: int = 1
    title: str = ""


class BaseParser(ABC):
    """Abstract base for document parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def supported_mime_types(self) -> list[str]:
        pass

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """Parse raw bytes into text and metadata."""
        pass
