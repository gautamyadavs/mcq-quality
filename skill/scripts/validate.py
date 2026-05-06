#!/usr/bin/env python3
"""
validate.py — Deterministic pre-checks for the 19 item-writing flaws.

This is the skill's bundled validator script. The skill body (SKILL.md)
references this script for the deterministic IWF checks; the AI runs it
locally as part of its review workflow.

In the integrated mcq-quality repo, this script is a thin wrapper around
the shared validator in mcq_quality.core. The MCP server's validate_mcq
tool and the workflow's Validator step also call into the same core
function, so all three paradigm layers stay in lockstep.

Usage:
    python validate.py < item.json
    python validate.py item.json
    python validate.py --stdin

Input JSON schema:
    {
        "stem": "string",
        "options": ["string", "string", ...],
        "correct_index": 0
    }

Output: JSON report with one entry per checkable IWF criterion.
"""

import json
import sys

# Import from the shared core. This is the integration spine: the same
# validate_item() runs whether you call this script, the MCP server's tool,
# or the workflow's Validator step.
try:
    from mcq_quality.core import validate_item
except ImportError:
    # Fallback for users who run this script directly from the skill folder
    # without having installed the package. We add the repo root to path and
    # import from there.
    import os
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, repo_root)
    from core import validate_item


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--stdin":
        with open(sys.argv[1]) as f:
            item = json.load(f)
    else:
        item = json.load(sys.stdin)

    report = validate_item(item)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
