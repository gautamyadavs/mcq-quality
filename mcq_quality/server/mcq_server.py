"""
mcq_server.py — MCP server for the integrated mcq-quality codebase.

Exposes the question bank, validator, and rubric as MCP tools and resources
so any MCP-aware client (Claude Desktop, Claude Code, Cursor, Cline, etc.)
can manage the bank from a chat. The validator the server uses is the same
function imported from mcq_quality.core that the skill script and the
workflow's Validator step call into.

Run directly:
    python -m mcq_quality.server

Or install and run via the configured entry point:
    mcq-quality-server
"""

import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import bank
from .similarity import find_similar_items
from mcq_quality.core import run_validator, summarize_validation


# Initialize the server and database on import
mcp = FastMCP("mcq-quality")
bank.init_db()

# Resolve reference docs relative to the package
# Reference docs live in the shared core, alongside the validator they describe.
_REFS_DIR = Path(__file__).parent.parent / "core" / "references"


# ---------- Tools: Bank operations ----------


@mcp.tool()
def bank_add_item(
    stem: str,
    options: list[str],
    correct_index: int,
    learning_objective: Optional[str] = None,
    blooms_level: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    rationales: Optional[dict] = None,
    learner_feedback: Optional[dict] = None,
    misconception_tags: Optional[list[str]] = None,
    quality_status: Optional[str] = None,
    created_by: Optional[str] = None,
    duplicate_threshold: float = 0.5,
    skip_duplicate_check: bool = False,
) -> dict:
    """
    Add a new MCQ to the bank.

    Automatically runs the 19-IWF validator and a duplicate similarity check
    against existing items. If duplicates are found above the threshold, the
    item is NOT added — the response includes the conflicts so the caller can
    decide whether to revise or skip the duplicate check.

    Args:
        stem: The question stem (the prompt the learner reads).
        options: List of answer choices in display order.
        correct_index: 0-based index of the correct answer.
        learning_objective: Optional LO this item assesses.
        blooms_level: Optional Bloom's level (Remember/Understand/Apply/Analyze/Evaluate/Create).
        category: Optional category label for organizing the bank.
        tags: Optional list of additional tags.
        rationales: Optional {correct: str, distractors: [{index, rationale}, ...]}.
        learner_feedback: Optional {correct: str, incorrect: [{index, feedback}, ...]}.
        misconception_tags: Optional list of misconception labels.
        quality_status: Optional status (Ready / Needs Minor Revision / etc.).
        created_by: Optional creator identifier.
        duplicate_threshold: Similarity above which to flag duplicates (default 0.5).
        skip_duplicate_check: Set True to add even if duplicates are found.

    Returns:
        On success: {"status": "added", "item": <full item dict>, "validation": <report>, "duplicates": []}
        On duplicate found: {"status": "duplicate_found", "duplicates": [...], "validation": <report>}
        On validation hard-fail (none currently — we let user decide): never
    """
    # Step 1: Run the deterministic validator
    validation = run_validator(stem, options, correct_index)

    # Step 2: Duplicate check
    duplicates = []
    if not skip_duplicate_check:
        existing = bank.list_items(limit=10_000)
        duplicates = find_similar_items(
            stem, options, existing, threshold=duplicate_threshold, top_k=5
        )
        if duplicates:
            return {
                "status": "duplicate_found",
                "message": (
                    f"{len(duplicates)} similar item(s) already in bank. "
                    "Review them, then either revise this item or call again with "
                    "skip_duplicate_check=True to add anyway."
                ),
                "duplicates": duplicates,
                "validation": validation,
                "validation_summary": summarize_validation(validation),
            }

    # Step 3: Add to bank
    item = bank.add_item(
        stem=stem,
        options=options,
        correct_index=correct_index,
        learning_objective=learning_objective,
        blooms_level=blooms_level,
        category=category,
        tags=tags,
        rationales=rationales,
        learner_feedback=learner_feedback,
        misconception_tags=misconception_tags,
        quality_status=quality_status,
        audit_results=validation,
        created_by=created_by,
    )

    return {
        "status": "added",
        "item": item,
        "validation": validation,
        "validation_summary": summarize_validation(validation),
        "duplicates": [],
    }


@mcp.tool()
def bank_update_item(
    item_id: int,
    changed_by: Optional[str] = None,
    change_note: Optional[str] = None,
    stem: Optional[str] = None,
    options: Optional[list[str]] = None,
    correct_index: Optional[int] = None,
    learning_objective: Optional[str] = None,
    blooms_level: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    rationales: Optional[dict] = None,
    learner_feedback: Optional[dict] = None,
    misconception_tags: Optional[list[str]] = None,
    quality_status: Optional[str] = None,
) -> dict:
    """
    Update an existing item by ID. Creates a new version snapshot.

    Re-runs the validator if stem, options, or correct_index changed, and
    stores updated audit_results.

    Provide a `change_note` describing what changed and why — this is stored
    in the version history and is invaluable for "why did we revise item 47
    last March" questions a year later.

    Returns the updated item, including its new version number.
    """
    current = bank.get_item(item_id)
    if current is None:
        return {"status": "not_found", "item_id": item_id}

    # Build update fields, only including the ones the caller passed
    fields = {}
    for k, v in {
        "stem": stem, "options": options, "correct_index": correct_index,
        "learning_objective": learning_objective, "blooms_level": blooms_level,
        "category": category, "tags": tags, "rationales": rationales,
        "learner_feedback": learner_feedback, "misconception_tags": misconception_tags,
        "quality_status": quality_status,
    }.items():
        if v is not None:
            fields[k] = v

    if not fields:
        return {"status": "no_changes", "item": current}

    # If the item content changed, re-run validation
    item_changed = any(k in fields for k in ("stem", "options", "correct_index"))
    if item_changed:
        new_stem = fields.get("stem", current["stem"])
        new_options = fields.get("options", current["options"])
        new_correct = fields.get("correct_index", current["correct_index"])
        validation = run_validator(new_stem, new_options, new_correct)
        fields["audit_results"] = validation
    else:
        validation = current.get("audit_results")

    updated = bank.update_item(
        item_id, changed_by=changed_by, change_note=change_note, **fields
    )

    return {
        "status": "updated",
        "item": updated,
        "validation": validation,
        "validation_summary": summarize_validation(validation) if validation else None,
        "version_change_recorded": True,
    }


@mcp.tool()
def bank_get_item(item_id: int) -> dict:
    """Retrieve a single item by ID. Returns {"status": "not_found"} if missing or deleted."""
    item = bank.get_item(item_id)
    if item is None:
        return {"status": "not_found", "item_id": item_id}
    return {"status": "ok", "item": item}


@mcp.tool()
def bank_list_items(
    category: Optional[str] = None,
    blooms_level: Optional[str] = None,
    quality_status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List items with optional filters.

    All filters are exact-match. Combine multiple filters to narrow results.
    Default limit is 50; raise it to scan the full bank.

    Returns: {"count": int, "items": [...]}
    """
    items = bank.list_items(
        category=category,
        blooms_level=blooms_level,
        quality_status=quality_status,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return {"count": len(items), "items": items}


@mcp.tool()
def bank_search_items(query: str, limit: int = 20) -> dict:
    """
    Substring search across stems and options. Case-insensitive.
    For semantic search, use bank_check_duplicate with the candidate stem.

    Returns: {"count": int, "items": [...]}
    """
    items = bank.search_items(query, limit=limit)
    return {"count": len(items), "items": items}


@mcp.tool()
def bank_check_duplicate(
    stem: str,
    options: Optional[list[str]] = None,
    threshold: float = 0.4,
    top_k: int = 5,
) -> dict:
    """
    Check whether a candidate stem is similar to anything already in the bank.

    Useful BEFORE drafting a new item — call this with a draft stem to find
    related items and avoid creating near-duplicates.

    Uses bigram-shingle Jaccard similarity over content words. Surface-level
    (catches rephrasings of the same question; misses semantic equivalence
    using different vocabulary).

    Threshold guidance:
    - 0.7+: Very likely duplicate — same item, possibly with minor wording changes
    - 0.5-0.7: Probable overlap — review carefully
    - 0.3-0.5: Some overlap — could be in the same topic family but distinct items
    - <0.3: Likely independent

    Returns: {"matches": [{"item_id", "item_stem", "similarity", "reason"}, ...]}
    """
    existing = bank.list_items(limit=10_000)
    matches = find_similar_items(
        stem, options, existing, threshold=threshold, top_k=top_k
    )
    return {"matches": matches, "checked_against": len(existing)}


@mcp.tool()
def validate_mcq(
    stem: str,
    options: list[str],
    correct_index: int,
) -> dict:
    """
    Run the deterministic 19-IWF validator on an item without storing it.

    This tool wraps mcq_quality.core.run_validator — the same function the
    skill's scripts/validate.py and the workflow's Validator step call into.
    Calling validate_mcq through MCP from the workflow demonstrates the
    workflow → MCP → core integration: same validator, different transport.

    Returns the full validation report with summary and per-criterion findings.
    Note: 7 of 19 criteria (#1, #2, #5, #7, #8, #13, #18) are semantic and
    cannot be checked deterministically — they're listed as remaining for
    LLM review.
    """
    return run_validator(stem, options, correct_index)


@mcp.tool()
def bank_delete_item(item_id: int, hard: bool = False) -> dict:
    """
    Delete an item. Soft delete by default (preserves history).
    Set hard=True to permanently remove the row (history is preserved separately).
    """
    success = bank.delete_item(item_id, hard=hard)
    return {
        "status": "deleted" if success else "not_found",
        "item_id": item_id,
        "hard": hard,
    }


@mcp.tool()
def bank_get_history(item_id: int) -> dict:
    """
    Return the full version history of an item. Each version is a snapshot
    plus metadata (when, by whom, why).

    Useful for: "show me how item 12 evolved over time" or "what was item 12
    before the last revision."
    """
    history = bank.get_history(item_id)
    return {"item_id": item_id, "version_count": len(history), "versions": history}


@mcp.tool()
def bank_get_stats() -> dict:
    """
    Aggregate statistics across the bank: total count, breakdowns by category,
    quality status, and Bloom's level.

    Useful for: "how big is my bank, is it balanced across topics, how many
    items still need revision."
    """
    return bank.get_stats()


# ---------- Resources: Reference content ----------


@mcp.resource("rubric://19-iwf")
def rubric_19_iwf() -> str:
    """The full 19 item-writing flaw criteria with definitions, examples, audit guidance."""
    path = _REFS_DIR / "19-iwf-rubric.md"
    if path.exists():
        return path.read_text()
    return "Rubric file not found. Expected at: " + str(path)


@mcp.resource("rubric://blooms")
def rubric_blooms() -> str:
    """Bloom's level inference from learning-objective verbs and stem-style guidance."""
    path = _REFS_DIR / "blooms-targeting.md"
    if path.exists():
        return path.read_text()
    return "Bloom's reference not found. Expected at: " + str(path)


@mcp.resource("bank://items")
def bank_items_resource() -> str:
    """Browsable JSON dump of all current items in the bank."""
    items = bank.list_items(limit=10_000)
    return json.dumps({"count": len(items), "items": items}, indent=2)


# ---------- Entry point ----------


def main():
    """Run the server over stdio (the standard MCP transport for local clients)."""
    mcp.run()


if __name__ == "__main__":
    main()
