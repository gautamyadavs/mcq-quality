# MCP Persistence Example: mcq-quality server

> **Note:** This file is a placeholder. The actual captured session needs to
> be recorded against a live AI client (Claude Code, Claude Desktop, Cursor,
> etc.) with the `mcq-quality` MCP server registered. The structure below
> shows what to capture; the placeholder text is what a real session would
> contain.

## Context

This file shows two separate AI-client conversations:

1. **Chat A** — the learner asks the AI to add an MCQ to the bank.
2. **Chat B** — a fresh, separate conversation. The learner asks the AI to
   list everything in the bank.

The point: **the MCQ from Chat A is visible in Chat B**. The bank persists
across conversations because the MCP server is a separate process holding
SQLite-backed live state. Skills can't do this; their instructions are static.

## Setup

Both chats happen with the `mcq-quality` MCP server registered per
[INSTALL_SERVER.md](../INSTALL_SERVER.md). Verify the server is loaded by
checking your client's tool inventory or logs at startup.

## Chat A — Adding an item

**User:** Add this MCQ to the bank: stem "What is the powerhouse of the
cell?", options ["Mitochondria", "Nucleus", "Ribosome"], correct index 0.

**[Tool call]:** The AI calls `bank_add_item` with the structured arguments.

**Tool result:**
```json
{
  "status": "added",
  "item_id": 1,
  "validation_summary": "Clean: no deterministic IWF issues detected.",
  "duplicate_check": "no near-duplicates found"
}
```

**Assistant:** Done. The MCQ has been added to the bank as item #1. The
validator passed all 12 deterministic IWF checks; the 7 semantic criteria
are still uncovered (they need LLM review).

---

*[The user closes Chat A and opens a new conversation.]*

---

## Chat B — Listing items in a fresh conversation

**User:** List everything currently in the bank.

**[Tool call]:** The AI calls `bank_list_items`.

**Tool result:**
```json
{
  "items": [
    {
      "id": 1,
      "stem": "What is the powerhouse of the cell?",
      "options": ["Mitochondria", "Nucleus", "Ribosome"],
      "correct_index": 0,
      "created_at": "...",
      "quality_status": null
    }
  ],
  "total": 1
}
```

**Assistant:** The bank currently has 1 item: a question about the
powerhouse of the cell, with three options and "Mitochondria" as the
correct answer.

## What to notice

1. **Two separate conversations.** Chat A's context is gone by the time
   Chat B starts. The AI in Chat B has no memory of Chat A.

2. **The bank persists anyway.** The item Chat A added shows up in Chat B's
   tool result. That state lives in the MCP server's SQLite database
   (`~/.mcq-quality/bank.db`), not in either conversation's context.

3. **A skill couldn't do this.** Skills package instructions; they don't
   maintain state across conversations. To get persistence, you need a
   process that *holds* state — that's what the MCP server provides.

4. **The validator is the same one the skill uses.** The `bank_add_item`
   tool calls into `mcq_quality.core.validate_item` (via `summarize_validation`).
   That's the same function the skill's `scripts/validate.py` calls, and the
   same one the workflow's Validator step calls. Three paradigm layers,
   one validator core.

## How to record a real session

1. Register the server per [INSTALL_SERVER.md](../INSTALL_SERVER.md).
2. Start a fresh chat (Chat A). Ask the AI to add an MCQ to the bank.
3. Close that chat and start a new conversation (Chat B).
4. Ask the AI to list everything in the bank.
5. Capture both conversations into this file, replacing the placeholders.
6. Include the tool calls and tool results — those make the persistence
   visible to learners reading the trace.
