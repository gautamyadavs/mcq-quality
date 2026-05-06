"""
similarity.py — Lightweight duplicate detection using word-shingle Jaccard similarity.

Approach: tokenize the stem (and optionally options), build n-gram shingles,
compute Jaccard similarity between the candidate and each existing item.

This is intentionally simple: no embeddings, no ML deps, no API calls.
For 30–500 items, brute-force comparison is fine (sub-second).
For larger banks, swap this module for sentence-transformers + pgvector.

Catches surface-level duplicates well (same stem rephrased, same options reordered).
Misses semantic equivalence ("spaced repetition" vs "distributed practice").
For semantic dup-detection, run an LLM check on the top-K candidates this returns.
"""

import re
from typing import Optional


_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "about",
    "and", "or", "but", "not", "as", "if", "then", "than", "that", "this",
    "these", "those", "it", "its", "do", "does", "did", "have", "has", "had",
    "which", "what", "how", "why", "when", "where", "who", "whom",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase content-word tokens of length >= 3, stop-words removed."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _shingles(tokens: list[str], n: int = 2) -> set[tuple[str, ...]]:
    """Generate n-gram shingles from a token list. Defaults to bigrams."""
    if len(tokens) < n:
        # Fall back to unigrams if too short for n-grams
        return {(t,) for t in tokens}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|. Returns 0.0 for two empty sets."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity_score(text_a: str, text_b: str, *, n: int = 1) -> float:
    """
    Compute similarity between two pieces of text. Range: 0.0 (different) to 1.0 (identical).

    Default uses unigrams over content words (stop words removed), which is robust to
    paraphrasing and word reordering. Set n=2 for bigrams if you want order sensitivity
    (catches surface-level duplicates more strictly but misses reordered paraphrases).
    """
    sa = _shingles(_tokenize(text_a), n=n)
    sb = _shingles(_tokenize(text_b), n=n)
    return jaccard(sa, sb)


def _item_signature(stem: str, options: Optional[list[str]] = None) -> str:
    """Build a comparison signature: stem + options concatenated."""
    parts = [stem]
    if options:
        parts.extend(options)
    return " ".join(parts)


def find_similar_items(
    candidate_stem: str,
    candidate_options: Optional[list[str]],
    existing_items: list[dict],
    *,
    threshold: float = 0.5,
    top_k: int = 5,
) -> list[dict]:
    """
    Compare a candidate item against existing items, return the top similar ones.

    Returns: list of {"item": <existing item dict>, "similarity": float, "reason": str}
    Sorted by similarity descending. Only items with similarity >= threshold are returned.

    The "reason" field gives a human-readable summary of why the similarity was high
    (stem-only, options-only, both).
    """
    if not existing_items:
        return []

    candidate_sig = _item_signature(candidate_stem, candidate_options)
    candidate_stem_only = candidate_stem
    candidate_options_str = " ".join(candidate_options) if candidate_options else ""

    results = []
    for item in existing_items:
        item_stem = item.get("stem", "")
        item_options = item.get("options", [])

        # Three similarity signals, take max
        sig_sim = similarity_score(candidate_sig, _item_signature(item_stem, item_options))
        stem_sim = similarity_score(candidate_stem_only, item_stem)
        opt_sim = similarity_score(candidate_options_str, " ".join(item_options)) if item_options else 0.0

        max_sim = max(sig_sim, stem_sim, opt_sim)

        if max_sim >= threshold:
            # Reason annotation
            if stem_sim >= max_sim - 0.05:
                reason = f"stem similarity {stem_sim:.2f}"
            elif opt_sim >= max_sim - 0.05:
                reason = f"options similarity {opt_sim:.2f}"
            else:
                reason = f"combined similarity {sig_sim:.2f}"
            results.append({
                "item_id": item.get("id"),
                "item_stem": item_stem,
                "similarity": round(max_sim, 3),
                "reason": reason,
            })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_k]
