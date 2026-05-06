"""
mcq_quality.workflow — multi-step agent pipeline for MCQ generation.

The pipeline orchestrates four roles:
  - Drafter: LLM, generates an initial MCQ from a learning objective
  - Validator: deterministic Python (19-IWF checks) OR via MCP server tool
  - Reviewer: LLM, judges semantic flaws and pedagogical fit
  - Reviser: LLM, fixes flagged issues

Two pipeline variants are exposed for pedagogical comparison:
  - run_naive_pipeline: runs all four agents in sequence every time
  - run_gated_pipeline: skips Reviewer/Reviser when Validator finds no issues

The Validator agent has two implementations that share the same return shape:
  - validator_agent: imports mcq_quality.core directly (default)
  - validator_agent_via_mcp: spawns the mcq-quality MCP server as a subprocess
    and calls validate_mcq through the protocol (when --use-mcp is set)

Run with:
    python -m mcq_quality.workflow              # standalone, naive vs gated
    python -m mcq_quality.workflow --use-mcp    # routes Validator through MCP
"""
