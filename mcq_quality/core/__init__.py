"""
mcq_quality.core — shared functions used by all three paradigm layers.

The validator function in this module is THE 19-IWF validator. The skill's
scripts/validate.py, the MCP server's validate_mcq tool, and the workflow's
Validator step all import from here. This is the integration spine: one
implementation of the validator, three paradigm wrappers around it.
"""

from .validator import validate_item, run_validator, summarize_validation

__all__ = ["validate_item", "run_validator", "summarize_validation"]
