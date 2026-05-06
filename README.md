# mcq-quality

An integrated codebase that demonstrates three patterns for extending AI assistants — **Skills**, **MCP servers**, and **multi-step agent workflows** — all built around the same problem: generating multiple-choice questions that satisfy the 19 item-writing flaw (IWF) criteria from Tarrant et al. (2006).

This repo is the companion artifact for the OLI module *Extending AI Assistants: Skills, MCP Servers, and Workflows*. The three paradigms are not parallel implementations; they layer on top of a shared validator core. A learner walking through the module installs once, then sees how each layer is built on what came before.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Workflow (multi-step pipeline)              │
│   Drafter (LLM) → Validator → Reviewer (LLM) → Reviser (LLM)    │
│                       │                                         │
│                       │  --use-mcp routes here                  │
│                       ▼                                         │
│            ┌─────────────────────────────────────────────┐      │
│            │  MCP server (mcq_quality.server)            │      │
│            │  Tools: validate_mcq, bank_add_item,        │      │
│            │         bank_list_items, bank_get_item, ... │      │
│            │                  │                          │      │
│            │                  ▼                          │      │
│            │     ┌──────────────────────────────────┐    │      │
│            │     │  Shared core (mcq_quality.core)  │    │      │
│            │     │  validate_item() — 19 IWF rules  │    │      │
│            │     │  rubric.md, output_schema.json   │    │      │
│            │     └──────────────────────────────────┘    │      │
│            └─────────────────────────────────────────────┘      │
│                                                                 │
│  Skill (skill/SKILL.md)                                         │
│  scripts/validate.py is a thin wrapper around the same core     │
│  references/19-iwf-rubric.md is the same rubric                 │
└─────────────────────────────────────────────────────────────────┘
```

The integration point is `mcq_quality.core.validate_item`. The skill's bundled script, the MCP server's `validate_mcq` tool, and the workflow's Validator step all call into this one function. Whatever path you reach the validator from, you get the same answer.

## What's in each layer

**Skill** (`skill/`): the open-standard Skill folder. SKILL.md instructs the AI on MCQ generation and review; `references/` carries the rubric and Bloom's targeting; `scripts/validate.py` is a deterministic 19-IWF check the AI can run locally.

**MCP server** (`mcq_quality/server/`): a FastMCP-based server exposing `validate_mcq` (the same validator the skill uses) plus a SQLite-backed question bank with `bank_add_item`, `bank_list_items`, `bank_get_item`, and several other tools. Run with `python -m mcq_quality.server`.

**Workflow** (`mcq_quality/workflow/`): a multi-step pipeline (Drafter → Validator → Reviewer → Reviser) implemented as four agent functions plus two pipeline variants (naive and gated). The Validator step has two interchangeable implementations: `validator_agent` (in-process import of the shared core) and `validator_agent_via_mcp` (workflow acts as an MCP client, spawning the server as a subprocess and calling `validate_mcq`). Use `--use-mcp` on the CLI to select the integrated path.

**Shared core** (`mcq_quality/core/`): the 19-IWF validator function, the rubric, the output schema. Imported by every layer.

## Quick install

```
git clone https://github.com/gautamyadavs/mcq-quality.git
cd mcq-quality
pip install -e .[anthropic]    # or [openai] or [all]
```

That's the whole Python install. To use each layer:

- **Skill:** symlink (or copy) the `skill/` folder into your AI client's skills directory. See [INSTALL_SKILL.md](./INSTALL_SKILL.md) for the per-client paths.
- **Server:** register `python -m mcq_quality.server` with your AI client. See [INSTALL_SERVER.md](./INSTALL_SERVER.md).
- **Workflow:** run `python -m mcq_quality.workflow compare "<learning objective>"` (set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` first). Add `--use-mcp` to route the Validator step through the MCP server.

## Running the demo

```
# Standalone workflow (Validator imports core directly)
python -m mcq_quality.workflow compare "Explain why retrieval practice beats rereading"

# Integrated workflow (Validator goes through the MCP server you also installed)
python -m mcq_quality.workflow compare "Explain why retrieval practice beats rereading" --use-mcp
```

Both produce the same MCQ; the second demonstrates the workflow as an MCP client.

## License

MIT.

## See also

- The OLI module that uses this repo: [Module-Extending-AI-Assistants](#) (link to be added when published)
- Tarrant et al. (2006), *Designing multiple-choice questions to assess pharmaceutical knowledge of pharmacy students* — source of the 19 item-writing flaws
- Anthropic's *Building Effective Agents* (Schluntz & Zhang, 2024) — terminology for workflow vs. autonomous agent
