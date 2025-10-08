from __future__ import annotations

"""Chunking utilities for LLM inputs.

This approximates tokens by characters to keep logic lightweight and portable. The
goal is to bound request sizes and costs, not to perfectly match tokenizer
behavior (which varies by model/provider).
"""

from typing import Iterable, List


def chunk_text(text: str, max_tokens: int) -> List[str]:
    """Split txt into chunks of up to `max_tokens` characters.

    Rationale: Many providers enforce token limits. Character-based chunking is
    a simple, over-approximate safeguard suitable for POC and test runs.
    """
    # Simplistic token approximation: characters as tokens fallback
    if max_tokens <= 0:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_tokens)
        chunks.append(text[start:end])
        start = end
    return chunks


def batch_items(items: Iterable[str], max_batch_chars: int) -> List[List[str]]:
    """Group strs into batches that do not exceed `max_batch_chars`.

    Useful for multi-file prompts or multi-snippet contexts.
    """
    batch: List[str] = []
    size = 0
    result: List[List[str]] = []
    for it in items:
        if size + len(it) > max_batch_chars and batch:
            result.append(batch)
            batch = []
            size = 0
        batch.append(it)
        size += len(it)
    if batch:
        result.append(batch)
    return result


