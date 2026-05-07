# MCQ Quality Coach (Custom GPT)

A Custom GPT that drafts and reviews multiple-choice questions against the 19 item-writing flaw criteria.

**Try it:** [chatgpt.com/g/g-6920b0d026a881918420de66d0e7805d-mcq-quality-coach](https://chatgpt.com/g/g-6920b0d026a881918420de66d0e7805d-mcq-quality-coach)

This GPT is the simplest pattern in this repository. The same MCQ-quality logic is also exposed as:
- a **Skill** (any compliant AI client, see [skill/SKILL.md](../skill/SKILL.md))
- an **MCP server** (cross-client, with persistent question bank, see [INSTALL_SERVER.md](../INSTALL_SERVER.md))
- a **Workflow** (deterministic checks + LLM review, see [mcq_quality/workflow/](../mcq_quality/workflow/))

The OLI module that accompanies this repo (CMU course 05840: Tools for Online Learning) walks through all four patterns in order, motivating each by what the previous one couldn't do.

## What's in this folder

- **INSTRUCTIONS.md** — the system instructions configured on the GPT
- (Knowledge files used by the GPT live at [skill/references/](../skill/references/) and are not duplicated here)

## Knowledge files referenced by the GPT

The GPT loads these three reference files at runtime:

- [`skill/references/19-iwf-rubric.md`](../skill/references/19-iwf-rubric.md) — the 19 item-writing flaw definitions and audit format
- [`skill/references/before-after-examples.md`](../skill/references/before-after-examples.md) — revision patterns
- [`skill/references/blooms-targeting.md`](../skill/references/blooms-targeting.md) — Bloom's level inference and stem style guidance

These are the same reference files the Skill version uses. The GPT and the Skill share knowledge sources; the difference is how the AI accesses them (uploaded to the GPT vs. loaded by the AI client when the Skill is invoked).
