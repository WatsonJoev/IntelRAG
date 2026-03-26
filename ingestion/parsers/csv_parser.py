"""CSV and XLSX parser using pandas."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from ingestion.parsers.base import BaseParser, ParsedDocument


class CSVParser(BaseParser):
    supported_extensions = [".csv", ".xlsx", ".xls"]
    supported_mime_types = [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        ext = Path(filename).suffix.lower()
        buf = io.BytesIO(content)
        if ext == ".csv":
            df = pd.read_csv(buf)
            text = df.to_string()
            return ParsedDocument(
                text=text.strip(),
                metadata={},
                page_count=1,
                title=filename,
            )
        df = pd.read_excel(buf, sheet_name=None)
        if isinstance(df, dict):
            parts = [s.to_string() for s in df.values()]
            text = "\n\n".join(parts)
            page_count = len(df)
            metadata = {"sheets": list(df.keys())}
        else:
            text = df.to_string()
            page_count = 1
            metadata = {}
        return ParsedDocument(
            text=text.strip(),
            metadata=metadata,
            page_count=page_count,
            title=filename,
        )
