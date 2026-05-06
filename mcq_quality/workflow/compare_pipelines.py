"""
compare_pipelines.py — Command-line entry point for the workflow.

Subcommands:
    python -m mcq_quality.workflow draft "<learning objective>"
    python -m mcq_quality.workflow naive "<learning objective>" [--use-mcp]
    python -m mcq_quality.workflow gated "<learning objective>" [--use-mcp]
    python -m mcq_quality.workflow compare "<learning objective>" [--use-mcp]

The --use-mcp flag routes the Validator step through the mcq-quality MCP
server (workflow as MCP client) instead of importing the validator directly
from mcq_quality.core. Both paths use the same validator function under the
hood; the difference is the calling path, which demonstrates the workflow →
MCP integration.
"""

import argparse
import sys

from .pipeline import (
    run_naive_pipeline,
    run_gated_pipeline,
    compare_pipelines,
)


def _print_item(item: dict) -> None:
    print(f"\nStem: {item.get('stem', '')}")
    for i, opt in enumerate(item.get("options", [])):
        marker = "*" if i == item.get("correct_index", -1) else " "
        print(f"  {marker} {chr(65+i)}) {opt}")
    if "blooms_level" in item:
        print(f"\nBloom's: {item['blooms_level']}")
    if "revision_notes" in item:
        print(f"Revision notes: {item['revision_notes']}")


def cmd_naive(args):
    item, trace = run_naive_pipeline(args.objective, use_mcp=args.use_mcp)
    print("\n=== NAIVE PIPELINE OUTPUT ===")
    if args.use_mcp:
        print("(Validator step routed through MCP server)")
    _print_item(item)
    print("\n=== TRACE ===")
    print(trace.summary())
    if args.save_trace:
        trace.save(args.save_trace)
        print(f"\nFull trace saved to {args.save_trace}")


def cmd_gated(args):
    item, trace = run_gated_pipeline(args.objective, use_mcp=args.use_mcp)
    print("\n=== GATED PIPELINE OUTPUT ===")
    if args.use_mcp:
        print("(Validator step routed through MCP server)")
    _print_item(item)
    print("\n=== TRACE ===")
    print(trace.summary())
    if args.save_trace:
        trace.save(args.save_trace)
        print(f"\nFull trace saved to {args.save_trace}")


def cmd_compare(args):
    result = compare_pipelines(args.objective, use_mcp=args.use_mcp)
    if args.use_mcp:
        print("\n(Validator step routed through MCP server in both pipelines)")
    print("\n=== NAIVE PIPELINE ===")
    _print_item(result["naive"]["final_item"])
    print(f"\nDuration: {result['naive']['duration_seconds']:.1f}s")
    print(f"Steps: {result['naive']['step_count']}, Final flags: {result['naive']['final_flags']}")

    print("\n=== GATED PIPELINE ===")
    _print_item(result["gated"]["final_item"])
    print(f"\nDuration: {result['gated']['duration_seconds']:.1f}s")
    print(f"Steps: {result['gated']['step_count']}, Final flags: {result['gated']['final_flags']}")

    print("\n=== COMPARISON ===")
    print(result["comparison"]["summary"])

    print("\n=== NAIVE OBSERVATIONS ===")
    for obs in result["naive"]["observations"]:
        print(f"  • {obs}")

    print("\n=== GATED OBSERVATIONS ===")
    for obs in result["gated"]["observations"]:
        print(f"  • {obs}")


def cmd_draft(args):
    """Just the draft step — no review, no revision."""
    from .agents import drafter_agent
    from .llm_client import LLMClient
    item, _step = drafter_agent(args.objective, LLMClient(), step_index=1)
    _print_item(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcq-quality.workflow",
        description="MCQ quality multi-step workflow (pedagogical artifact)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, fn in [
        ("draft", cmd_draft),
        ("naive", cmd_naive),
        ("gated", cmd_gated),
        ("compare", cmd_compare),
    ]:
        p = sub.add_parser(name, help=fn.__doc__)
        p.add_argument("objective", help="Learning objective text")
        if name in ("naive", "gated", "compare"):
            p.add_argument(
                "--use-mcp",
                action="store_true",
                help=(
                    "Route the Validator step through the mcq-quality MCP "
                    "server (spawned as a subprocess via stdio) instead of "
                    "in-process import."
                ),
            )
        else:
            p.set_defaults(use_mcp=False)
        if name in ("naive", "gated"):
            p.add_argument(
                "--save-trace",
                help="Path to save full JSON trace (e.g. trace.json)",
            )
        p.set_defaults(func=fn)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
