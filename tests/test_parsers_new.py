# tests/test_parsers_new.py
import io
from pptx import Presentation
from pptx.util import Inches


def make_pptx_bytes(slide_text: str = "Hello PPTX World") -> bytes:
    prs = Presentation()
    slide_layout = prs.slide_layouts[5]
    slide = prs.slides.add_slide(slide_layout)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    txBox.text_frame.text = slide_text
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_pptx_parser_extracts_text():
    from ingestion.parsers.pptx_parser import PPTXParser
    parser = PPTXParser()
    result = parser.parse(make_pptx_bytes("Hello PPTX"), "test.pptx")
    assert "Hello PPTX" in result.text
    assert result.page_count >= 1


def test_pptx_parser_supported_extensions():
    from ingestion.parsers.pptx_parser import PPTXParser
    p = PPTXParser()
    assert ".pptx" in p.supported_extensions
