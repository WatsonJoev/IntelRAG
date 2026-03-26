"""Tests for ingestion parsers."""
from __future__ import annotations

from ingestion.parsers.factory import get_parser_for_filename, get_parser_for_content
from ingestion.parsers.txt_parser import TXTParser


def test_get_parser_for_filename() -> None:
    assert get_parser_for_filename("a.pdf") is not None
    assert get_parser_for_filename("a.docx") is not None
    assert get_parser_for_filename("a.txt") is not None
    assert get_parser_for_filename("a.csv") is not None
    assert get_parser_for_filename("a.xyz") is None


def test_txt_parser() -> None:
    p = TXTParser()
    out = p.parse(b"Hello world", "test.txt")
    assert out.text == "Hello world"
    assert out.page_count == 1


def test_txt_parser_utf8() -> None:
    p = TXTParser()
    out = p.parse("Café".encode("utf-8"), "t.txt")
    assert "Café" in out.text
