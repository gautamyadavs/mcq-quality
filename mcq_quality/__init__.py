"""
mcq_quality — integrated codebase demonstrating Skills, MCP, and multi-step
agent workflows for MCQ generation against the 19 item-writing flaws.

The package layers three paradigm implementations on top of a shared core:

  - mcq_quality.core: the 19-IWF validator, rubric, and schema (shared)
  - mcq_quality.server: MCP server exposing the validator + question bank
  - mcq_quality.workflow: multi-step pipeline (Drafter, Validator, Reviewer,
    Reviser) with optional --use-mcp mode that calls the server's tools

The skill paradigm is implemented as a plain folder at ../skill/ in the repo
root (not a Python subpackage); see skill/SKILL.md and skill/scripts/validate.py.
"""

__version__ = "0.1.0"
