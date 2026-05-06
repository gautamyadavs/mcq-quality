# Skill Conversation Example: mcq-quality

> **Note:** This file is a placeholder. The actual captured session needs to
> be recorded against a live AI client (Claude Code, Codex CLI, Cursor, etc.)
> with the `mcq-quality` skill installed. The structure below shows what to
> capture; the placeholder text is what a real session would contain.

## Context

This is a captured AI client conversation showing the `mcq-quality` skill in
action. The learner installed the skill following [INSTALL_SKILL.md](../INSTALL_SKILL.md)
and asked the AI to write quiz questions on a topic. The skill activates
automatically — the user does NOT name the skill; the AI matches the
`description` field in `SKILL.md` against the user's request.

## Conversation

**User:** Write me three quiz questions about photosynthesis.

**[Skill activation]:** The AI client surfaces (or logs) that it activated
the `mcq-quality` skill before responding.

**Assistant:** *(SKILL.md body now in context. The AI follows its workflow:
identifies assessment target, infers Bloom's level, drafts a question,
runs `scripts/validate.py` for the deterministic 19-IWF audit, revises if
needed, then produces the final item. It does this three times.)*

```json
[
  {
    "stem": "...",
    "options": ["...", "...", "..."],
    "correct_index": 0,
    "blooms_level": "Apply",
    "rationale": "...",
    "feedback": {...},
    "hint": "..."
  },
  ...
]
```

The output follows the schema in `skill/assets/output-schema.json`.

## What to notice

1. **The user didn't name the skill.** The AI matched "quiz questions" to the
   skill's description and activated it implicitly. That's progressive
   disclosure: the skill metadata (frontmatter) was loaded at startup; the
   skill body loaded only when the AI decided to use it.

2. **The questions follow the 19-IWF format.** No length cues, no absolutes
   in distractors, no "all of the above," parallel option structure. The AI
   applied the rubric without you specifying it.

3. **The AI ran a script.** Watch your client's output for the validator
   running — if your client surfaces script execution, you'll see the AI
   call `scripts/validate.py` to check its own draft before showing it to
   you. The validator function (in `mcq_quality.core`) is the same one the
   MCP server uses and the workflow's Validator step uses.

## How to record a real session

1. Install the skill per [INSTALL_SKILL.md](../INSTALL_SKILL.md).
2. Start a fresh chat in your AI client.
3. Ask: "Write me three quiz questions about photosynthesis."
4. Copy the conversation (request, skill activation, response) into this file,
   replacing the placeholder above.
5. If your client surfaces tool execution (script calls, etc.), include those
   in the capture so learners can see the validator running.
