from core.schemas import RetrievedChunk
from core.prompt_builder import build_messages


def _chunk(text: str, doc: str = "report.pdf", page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(text=text, doc_name=doc, page_number=page, chunk_index=0, score=0.8)


def test_messages_list_structure():
    chunks = [_chunk("The deadline is Q3.")]
    msgs = build_messages("When is the deadline?", chunks, history=[])
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    assert roles[-1] == "user"


def test_source_context_in_user_message():
    chunks = [_chunk("Revenue was $10M.", "finance.pdf", 4)]
    msgs = build_messages("What was revenue?", chunks, history=[])
    combined = " ".join(m["content"] for m in msgs)
    assert "[Source 1]" in combined
    assert "finance.pdf" in combined
    assert "Revenue was $10M" in combined


def test_conversation_history_included():
    chunks = [_chunk("text")]
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
    ]
    msgs = build_messages("Follow-up", chunks, history=history)
    contents = [m["content"] for m in msgs]
    assert any("First question" in c for c in contents)


def test_no_sources_triggers_fallback_instruction():
    msgs = build_messages("Who are you?", chunks=[], history=[])
    system_content = msgs[0]["content"]
    assert "don't have enough information" in system_content.lower() or "i don't know" in system_content.lower()
