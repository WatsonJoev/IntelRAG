"""
Local file store for raw document uploads.
Write-once storage at {base_path}/{doc_id}/{filename}.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO

from config.logging_config import get_logger

logger = get_logger(__name__)


class FileStore:
    """Store and retrieve raw uploaded files by doc_id and filename."""

    def __init__(self, base_path: str | Path = "./data/uploads") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _doc_dir(self, doc_id: str) -> Path:
        d = self.base_path / doc_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(
        self,
        doc_id: str,
        filename: str,
        content: bytes | BinaryIO,
    ) -> str:
        """
        Save file to {base_path}/{doc_id}/{filename}.
        Returns path relative to base_path.
        """
        doc_dir = self._doc_dir(doc_id)
        dest = doc_dir / self._sanitize_filename(filename)
        if hasattr(content, "read"):
            with open(dest, "wb") as f:
                shutil.copyfileobj(content, f)
        else:
            dest.write_bytes(content)
        rel = dest.relative_to(self.base_path)
        logger.info("file_saved", doc_id=doc_id, filename=filename, path=str(rel))
        return str(rel)

    def get_path(self, doc_id: str, filename: str) -> Path:
        """Return full Path to stored file. Does not check existence."""
        return self.base_path / doc_id / self._sanitize_filename(filename)

    def exists(self, doc_id: str, filename: str) -> bool:
        return self.get_path(doc_id, filename).is_file()

    def read(self, doc_id: str, filename: str) -> bytes:
        path = self.get_path(doc_id, filename)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_bytes()

    def delete_document(self, doc_id: str) -> None:
        """Remove entire document directory."""
        doc_dir = self.base_path / doc_id
        if doc_dir.is_dir():
            shutil.rmtree(doc_dir)
            logger.info("document_deleted", doc_id=doc_id)

    def content_hash(self, content: bytes) -> str:
        """SHA-256 hash of content for duplicate detection."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Keep only safe filename characters."""
        safe = "".join(c for c in name if c.isalnum() or c in "._- ")
        return safe.strip() or "document"
