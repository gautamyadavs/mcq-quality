# examples/

Captured artifacts from running the three layers of the mcq-quality codebase.
Each file corresponds to one of the OLI module's LO pages, and each file is
the fallback artifact for learners who can't run the corresponding layer
locally (no API key, locked-down environment, install fails).

| File | Layer | LO page | Status |
|---|---|---|---|
| `lo1-skill-conversation.md` | Skill | LO 1 | placeholder; capture against a real AI client |
| `lo2-mcp-persistence.md` | MCP server | LO 2 | placeholder; capture across two real chats |
| `lo3-workflow-traces.md` | Workflow | LO 3 | **real**, generated from running the integrated workflow |

The LO 3 trace is real because the workflow's Validator step runs without
needing an AI client (it's deterministic Python plus the MCP subprocess; no
LLM API key required for that step).

LO 1 and LO 2 placeholders need to be captured against actual AI client
conversations because skill activation and tool calling are mediated by the
client. The placeholder files describe what to capture and where to put it.
