# Installing mcq-quality

This walks through installing the integrated repo end-to-end. If you only need one layer (skill, server, or workflow), the per-layer guides below have the minimum steps.

## 1. Python install (required for all layers)

```
git clone https://github.com/gautamyadavs/mcq-quality.git
cd mcq-quality
pip install -e .[anthropic]
```

Replace `[anthropic]` with `[openai]` if you prefer OpenAI, or `[all]` to install both LLM client libraries. The base install (no extras) is enough if you only need the Skill or the MCP server (which don't make LLM calls themselves).

Verify the install:

```
python -c "from mcq_quality.core import validate_item; print('core OK')"
python -c "from mcq_quality.server.mcq_server import mcp; print('server OK')"
python -c "from mcq_quality.workflow.pipeline import compare_pipelines; print('workflow OK')"
```

## 2. Skill install (LO 1)

The skill is a folder; AI clients load it from a client-specific path. See [INSTALL_SKILL.md](./INSTALL_SKILL.md) for paths per client (Codex CLI, Claude Code, Cursor, Cline).

The simplest case (Claude Code on macOS or Linux):

```
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skill" ~/.claude/skills/mcq-quality
```

Open a fresh chat in your AI client and ask:

> "Write me three quiz questions about photosynthesis."

The client should activate the `mcq-quality` skill (you'll see it surface skill activation if your client displays this) and produce three IWF-compliant MCQs without you naming the skill.

## 3. MCP server install (LO 2)

Register the server with your AI client. See [INSTALL_SERVER.md](./INSTALL_SERVER.md) for client-specific config syntax.

The simplest case (Claude Code, edit `~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "mcq-quality": {
      "command": "python",
      "args": ["-m", "mcq_quality.server"]
    }
  }
}
```

Restart your AI client. Open a chat and ask:

> "Add this MCQ to the bank: stem 'What is the powerhouse of the cell?', options ['Mitochondria', 'Nucleus', 'Ribosome'], correct index 0."

The AI should call the `bank_add_item` tool. Open a separate chat and ask:

> "List all items in the bank."

You should see the item you added. The bank persists across chats and across clients because it's a separate process holding live state.

## 4. Workflow install (LO 3)

The workflow runs locally; no AI client involvement. Set an LLM API key:

```
export ANTHROPIC_API_KEY="..."   # or OPENAI_API_KEY
```

Run the standalone variant:

```
python -m mcq_quality.workflow compare "Explain why retrieval practice beats rereading"
```

This runs the Drafter (LLM), Validator (in-process), Reviewer (LLM), and Reviser (LLM) in both naive and gated modes, then compares.

Run the integrated variant (workflow as MCP client to the server from step 3):

```
python -m mcq_quality.workflow compare "Explain why retrieval practice beats rereading" --use-mcp
```

The `--use-mcp` flag routes the Validator step through the MCP server. The workflow spawns the server as a subprocess via stdio, calls `validate_mcq`, and unwraps the structured result. Same validator function, different transport.

## Troubleshooting

**`ModuleNotFoundError: mcq_quality`** — you didn't run `pip install -e .` from the repo root, or you're in a different Python environment. Check `which python3` and `pip show mcq-quality`.

**`No LLM API key found`** — set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your environment before running the workflow. The skill and server don't need an API key; only the workflow does (its Drafter, Reviewer, and Reviser are LLM-driven).

**Skill doesn't activate** — your AI client may not support skills. Check that the path you symlinked into is the right one for your client (see [INSTALL_SKILL.md](./INSTALL_SKILL.md)).

**MCP server doesn't show up in your client** — confirm `python -m mcq_quality.server` runs from your terminal without errors. Some AI clients require the absolute path to `python` in the config; use `which python3` to find it.
