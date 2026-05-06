# Installing the mcq-quality skill

The skill is a folder (`skill/`) with `SKILL.md`, `references/`, `scripts/`, and `assets/`. AI clients that support the open Skills standard load skills from a client-specific directory; you make the skill available by symlinking or copying the `skill/` folder into that directory under the name `mcq-quality`.

## Claude Code (macOS, Linux)

```
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skill" ~/.claude/skills/mcq-quality
```

## Codex CLI (macOS, Linux)

```
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skill" ~/.codex/skills/mcq-quality
```

## Cursor

Cursor's skills support is evolving. As of writing, place skills in `~/.cursor/skills/` if your version supports them. Check Cursor's documentation for the current path.

## Claude Desktop / Cline / other clients

Consult your client's documentation for the skills directory. The skill folder is portable; the client just needs to know where to find it.

## Testing the install

Open a fresh chat and ask:

> "Write me three quiz questions about photosynthesis."

The skill should activate (your client may display "Activating skill: mcq-quality" or similar). The output should be three multiple-choice questions in the open output schema (stem, options, correct_index, blooms_level, rationale, feedback, hint).

Note: skill activation is implicit. The AI matches your request against each installed skill's `description` field. If your request doesn't match the trigger phrases (`quiz questions`, `MCQ`, `multiple-choice`, `test items`, `assessment items`), the skill won't fire — which is correct behavior. To test that the skill is installed, ask something it should match.

## What this skill does

- Generates one MCQ per request from a learning objective
- Targets a Bloom's level inferred from the objective
- Defaults to 3 options (research-backed: Vegada et al., 2016)
- Runs a deterministic 19-IWF audit before returning (via `scripts/validate.py`, which calls into `mcq_quality.core`)
- Asks for clarification only when the learning objective is ambiguous

## Troubleshooting

**Skill is in the right directory but doesn't activate** — open the AI client's logs (most clients have a "skills loaded" message at startup). If `mcq-quality` isn't listed, check that `SKILL.md`'s frontmatter is valid YAML (no missing colons, no bad indentation).

**AI says it doesn't know the rubric** — the skill loads the rubric on demand, not at startup. The skill will read `references/19-iwf-rubric.md` itself when needed; you don't need to instruct it to.

**Script errors when AI runs `scripts/validate.py`** — the script imports from `mcq_quality.core`. Make sure the package is installed (`pip install -e .` from the repo root) in the Python environment your AI client uses.
