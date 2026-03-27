"""Prompt builder: assembles messages list for OpenRouter/OpenAI chat format."""
from __future__ import annotations

from core.schemas import RetrievedChunk

SYSTEM_PROMPT = """You are IntelRAG, an enterprise knowledge assistant.
Answer questions using the context provided below.
- Always attempt to answer using the provided context, even if it is partial or incomplete.
- Cite sources inline as [Source N].
- If the context contains relevant information, synthesize and summarize it clearly.
- Only say you cannot answer if the context contains absolutely no information related to the question.
- Never invent facts not present in the context. Be concise and professional."""


def build_messages(
    query: str,
    chunks: list,
    history: list,
) -> list:
    """Return a messages list in OpenAI chat format."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chunks:
        source_blocks = "\n\n".join(
            f"[Source {i + 1}] {c.doc_name}"
            + (f", page {c.page_number}" if c.page_number else "")
            + f":\n{c.text}"
            for i, c in enumerate(chunks)
        )
        context_msg = f"CONTEXT:\n{source_blocks}"
        messages.append({"role": "system", "content": context_msg})

    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": query})
    return messages
