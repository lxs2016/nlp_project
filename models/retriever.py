"""MemoryRetriever: encode state + intent, retrieve Top-K from runtime memory (sentence-transformers)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.memory import Memory

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _encoder = False
    return _encoder


def retrieve(
    memory: "Memory",
    state_summary: str,
    intent: str,
    k: int = 5,
    recent_n: int = 3,
) -> str:
    """
    Return retrieved_context: Top-K by similarity + recent_n by time, concatenated.
    If sentence_transformers not available, returns recent_n summaries only.
    """
    entries = memory.entries_for_retrieval()
    if not entries:
        return ""
    summaries = [e[0] for e in entries]
    query = f"{state_summary} intent: {intent}".strip()
    encoder = _get_encoder()
    if encoder is False:
        # Fallback: recent N only
        recent = memory.recent_n(recent_n)
        return "\n".join(recent) if recent else ""

    from numpy import dot
    from numpy.linalg import norm
    q_vec = encoder.encode([query], convert_to_numpy=True)[0]
    doc_vecs = encoder.encode(summaries, convert_to_numpy=True)
    scores = [float(dot(q_vec, v) / (norm(q_vec) * norm(v) + 1e-9)) for v in doc_vecs]
    idx_scores = list(enumerate(scores))
    idx_scores.sort(key=lambda x: -x[1])
    top_indices = [i for i, _ in idx_scores[:k]]
    top_summaries = [summaries[i] for i in top_indices]
    recent = memory.recent_n(recent_n)
    seen = set()
    out = []
    for s in top_summaries:
        if s not in seen:
            seen.add(s)
            out.append(s)
    for s in recent:
        if s not in seen:
            out.append(s)
    return "\n".join(out) if out else ""
