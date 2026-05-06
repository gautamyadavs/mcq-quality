# Installing the mcq-quality MCP server

The server runs as a subprocess of your AI client, communicating via stdio. You register it once in your client's MCP config; the client launches it on demand.

The server exposes 10 tools and 3 resources:

**Tools**
- `validate_mcq` — run the 19-IWF validator on an item without storing it (the integration point used by the workflow's `--use-mcp` mode)
- `bank_add_item` — add an MCQ to the persistent question bank (with auto-validation and duplicate check)
- `bank_update_item` — update an existing item; creates a new version snapshot
- `bank_get_item` — retrieve an item by ID
- `bank_list_items` — list with filters (category, tags, quality status)
- `bank_search_items` — substring search across stems and options
- `bank_check_duplicate` — check whether a draft is similar to existing items
- `bank_delete_item` — soft delete (default) or hard delete
- `bank_get_history` — show the version history of an item
- `bank_get_stats` — bank-wide stats (counts by category, quality distribution)

**Resources**
- `rubric://19-iwf` — the full 19-item-writing-flaw rubric (markdown)
- `rubric://blooms` — Bloom's taxonomy targeting reference (markdown)
- `bank://items` — the current bank as a JSON list

The bank is stored at `~/.mcq-quality/bank.db` by default. Override with `MCQ_BANK_DB_PATH=/some/other/path`.

## Claude Code

Edit `~/.claude/mcp.json`:

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

Restart Claude Code. The server tools should appear in the tool inventory.

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Quit and relaunch Claude Desktop.

## Codex CLI

Codex CLI uses a per-project or per-user config. Add to your config:

```toml
[[mcp_servers]]
name = "mcq-quality"
command = "python"
args = ["-m", "mcq_quality.server"]
```

## Cursor / Cline

Both clients support MCP servers; consult their documentation for the current config syntax. The `command` and `args` are the same as above.

## Testing

After registering and restarting your client, open a chat and ask:

> "Add this MCQ to the bank: stem 'What is the powerhouse of the cell?', options ['Mitochondria', 'Nucleus', 'Ribosome'], correct index 0."

You should see the AI call `bank_add_item`. The structured response will include the new item ID and the validation summary.

Then open a *separate* chat and ask:

> "List all items in the bank."

The AI should call `bank_list_items` and show you the item from the previous chat. The bank persists across conversations because the server is a separate process holding the SQLite DB.

## Troubleshooting

**`python` not found** — some clients need an absolute path to Python. Replace `"python"` with the output of `which python3`.

**Server starts but no tools appear** — check the AI client's logs. The client may log MCP handshake errors. Common cause: Python environment mismatch (the `python` your client launches doesn't have `mcq-quality` installed).

**Bank file not created** — the server creates `~/.mcq-quality/bank.db` lazily on first write. If it doesn't appear, check filesystem permissions on your home directory or set `MCQ_BANK_DB_PATH` to a writable location.

**Want to inspect the bank directly?** It's plain SQLite:

```
sqlite3 ~/.mcq-quality/bank.db
.tables
SELECT id, stem FROM items;
```
