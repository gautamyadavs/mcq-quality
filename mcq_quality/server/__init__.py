"""
mcq_quality.server — MCP server exposing the question bank as tools.

The server is one of three paradigm layers in the integrated mcq-quality
codebase. It uses the validator from mcq_quality.core (same function the
skill's script and the workflow's Validator step call into) and adds:
- A SQLite-backed question bank (live external state, persists across chats)
- Tools for adding, listing, getting, updating, and removing items
- A duplicate-similarity check before insertion
- Resource access to the rubric and Bloom's targeting reference

Run with:
    python -m mcq_quality.server
"""
