"""
pipeline.py — Orchestrate the agents.

Provides TWO pipeline variants for pedagogical comparison:

  1. run_naive_pipeline: Drafter → Validator → Reviewer → Reviser. Always runs
     all four agents in sequence. This is what students will naturally build
     when they reach for "let's add more agents." Demonstrates:
     - Latency cost (4 LLM calls + 1 deterministic step)
     - Sycophancy risk (Reviewer can approve flawed items)
     - Revision regression risk (Reviser may introduce new issues)

  2. run_gated_pipeline: Drafter → Validator → [conditional] Reviewer →
     [conditional] Reviser. Only invokes downstream agents if upstream agents
     find issues. Demonstrates:
     - Lower latency on items the gate fires for
     - Often comparable or better quality (skipped revisions can't introduce
       regressions)
     - The general principle: conditional invocation is almost always
       better than unconditional sequential agent chains.

Both pipelines share the same agents and produce the same trace format. The
OLI module asks students to run both on the same input and compare.

For an honest comparison, compare_pipelines() drafts ONCE and feeds the same
draft into both pipelines — otherwise differences could come from sampling
variance in the Drafter, not from the orchestration design.
"""

import time
from typing import Optional

from .agents import (
    drafter_agent,
    validator_agent,
    validator_agent_via_mcp,
    reviewer_agent,
    reviser_agent,
)
from .llm_client import LLMClient
from .trace import PipelineTrace


def _select_validator(use_mcp: bool):
    """Pick the validator agent based on transport mode.

    use_mcp=False: in-process import of mcq_quality.core (default; works
        without any server running).
    use_mcp=True:  spawn the mcq-quality MCP server as a subprocess and call
        its validate_mcq tool through the protocol. Same return shape, same
        validator function under the hood; the difference is the calling path
        and the demonstration of workflow → MCP integration.
    """
    return validator_agent_via_mcp if use_mcp else validator_agent


def _run_naive_from_draft(
    learning_objective: str,
    draft: dict,
    draft_step,
    llm: LLMClient,
    use_mcp: bool = False,
) -> tuple[dict, PipelineTrace]:
    """Naive pipeline starting from a pre-existing draft.

    Used by both run_naive_pipeline (which generates the draft itself) and
    compare_pipelines (which generates one draft and feeds it to both
    pipelines for an honest comparison).

    use_mcp routes the Validator step through the MCP server (workflow as
    MCP client) rather than via direct in-process import. See _select_validator.
    """
    validate = _select_validator(use_mcp)

    trace = PipelineTrace(
        pipeline_name="naive_sequential",
        started_at=time.time(),
        initial_input={"learning_objective": learning_objective},
    )
    trace.add_step(draft_step)

    # Step 2: Validate (deterministic; via MCP if use_mcp=True)
    val_out, step = validate(draft, step_index=2)
    trace.add_step(step)

    # Step 3: Pedagogical review (always runs in naive pipeline)
    review_out, step = reviewer_agent(
        draft, learning_objective, val_out["validation_report"], llm, step_index=3
    )
    trace.add_step(step)
    for note in step.notes:
        if note.startswith("PEDAGOGICAL OBSERVATION"):
            trace.add_observation(note)

    # Step 4: Revise (always runs in naive pipeline, even if no issues)
    revised, step = reviser_agent(
        draft, val_out["validation_report"], review_out, llm, step_index=4
    )
    trace.add_step(step)

    # Pedagogical instrumentation: did the reviser introduce new issues?
    # The post-revision validation always uses the in-process path; spawning
    # an MCP server twice per pipeline run would be wasteful and the
    # instrumentation outcome is the same either way.
    revised_val = validator_agent(revised, step_index=99)[0]
    _record_revision_outcomes(
        trace, val_out["validation_report"], revised_val["validation_report"]
    )

    trace.finalize(final_output=revised)
    return revised, trace


def _run_gated_from_draft(
    learning_objective: str,
    draft: dict,
    draft_step,
    llm: LLMClient,
    use_mcp: bool = False,
) -> tuple[dict, PipelineTrace]:
    """Gated pipeline starting from a pre-existing draft."""
    validate = _select_validator(use_mcp)

    trace = PipelineTrace(
        pipeline_name="gated_conditional",
        started_at=time.time(),
        initial_input={"learning_objective": learning_objective},
    )
    trace.add_step(draft_step)

    # Step 2: Validate (via MCP if use_mcp=True)
    val_out, step = validate(draft, step_index=2)
    trace.add_step(step)

    flagged = [
        r for r in val_out["validation_report"]["results"] if r["status"] == "Flagged"
    ]
    minor = [
        r for r in val_out["validation_report"]["results"] if r["status"] == "Minor risk"
    ]

    # Gate: skip review and revision entirely if validator is happy.
    # NOTE: This is a deliberate teaching tradeoff. The deterministic validator
    # only catches surface-level flaws (12 of 19 IWFs). Semantic flaws —
    # ambiguity (#1), implausible distractors (#2), gratuitous information (#5),
    # convergence (#7), logical clues (#8), unfocused stems (#13), multiple
    # defensible answers (#18) — are NOT checked here. Skipping the gate is
    # fast and saves cost on items that look surface-clean, but it can let
    # semantic flaws through. The OLI module discussion should make this
    # tradeoff explicit to students.
    if not flagged and not minor:
        trace.add_observation(
            "GATING: Deterministic validator found no surface-level flags. "
            "Skipping semantic reviewer and reviser. Saved 2 LLM calls vs. "
            "naive pipeline. NOTE: the validator only catches 12 of 19 IWFs; "
            "semantic flaws (#1 ambiguity, #2 implausible distractors, "
            "#5 gratuitous information, #7 convergence cues, #8 logical clues, "
            "#13 unfocused stems, #18 multiple defensible answers) are NOT "
            "checked when this gate fires. The OLI module asks students to "
            "weigh this tradeoff: is the latency win worth the semantic-quality "
            "risk?"
        )
        trace.finalize(final_output=draft)
        return draft, trace

    # Step 3: Review (conditional — only if there's something to review)
    review_out, step = reviewer_agent(
        draft, learning_objective, val_out["validation_report"], llm, step_index=3
    )
    trace.add_step(step)
    for note in step.notes:
        if note.startswith("PEDAGOGICAL OBSERVATION"):
            trace.add_observation(note)

    # Gate: skip revision if reviewer approved AND validator only had minor risks
    reviewer_verdict = review_out.get("overall", "approve")
    if reviewer_verdict == "approve" and not flagged:
        trace.add_observation(
            "GATING: Reviewer approved and validator had only minor risks. "
            "Skipping reviser. Saved 1 LLM call vs. naive pipeline."
        )
        trace.finalize(final_output=draft)
        return draft, trace

    # Step 4: Revise
    revised, step = reviser_agent(
        draft, val_out["validation_report"], review_out, llm, step_index=4
    )
    trace.add_step(step)

    revised_val = validator_agent(revised, step_index=99)[0]
    _record_revision_outcomes(
        trace, val_out["validation_report"], revised_val["validation_report"]
    )

    trace.finalize(final_output=revised)
    return revised, trace


def _record_revision_outcomes(
    trace: PipelineTrace,
    original_report: dict,
    revised_report: dict,
) -> None:
    """Record whether the Reviser fixed issues, introduced new ones, or both.

    Note: this only catches NEW criterion numbers. Same-criterion regressions
    (e.g., a different option also has #4 length cue) are not detected here.
    """
    original_flagged = {
        r["criterion"]
        for r in original_report["results"]
        if r["status"] == "Flagged"
    }
    revised_flagged = {
        r["criterion"]
        for r in revised_report["results"]
        if r["status"] == "Flagged"
    }
    fixed = original_flagged - revised_flagged
    introduced = revised_flagged - original_flagged
    if introduced:
        trace.add_observation(
            f"REVISION REGRESSION: Reviser introduced new flagged criteria "
            f"{sorted(introduced)} while attempting to fix {sorted(original_flagged)}. "
            f"This is the regression problem the OLI module discusses — agents "
            f"that revise can break things they weren't asked to change."
        )
    if fixed:
        trace.add_observation(
            f"Reviser successfully fixed criteria {sorted(fixed)}."
        )


def run_naive_pipeline(
    learning_objective: str,
    llm: Optional[LLMClient] = None,
    use_mcp: bool = False,
) -> tuple[dict, PipelineTrace]:
    """Run all four agents in sequence, regardless of intermediate findings.

    Returns: (final_item, full_trace)

    use_mcp routes the Validator step through the MCP server.
    """
    llm = llm or LLMClient()
    draft, draft_step = drafter_agent(learning_objective, llm, step_index=1)
    return _run_naive_from_draft(learning_objective, draft, draft_step, llm, use_mcp=use_mcp)


def run_gated_pipeline(
    learning_objective: str,
    llm: Optional[LLMClient] = None,
    use_mcp: bool = False,
) -> tuple[dict, PipelineTrace]:
    """Run agents conditionally based on upstream findings.

    The pedagogical comparison: same agents, same task, but skipping
    unnecessary steps. Students should observe lower latency with
    comparable (sometimes higher) quality on items the gate fires for.

    use_mcp routes the Validator step through the MCP server.
    """
    llm = llm or LLMClient()
    draft, draft_step = drafter_agent(learning_objective, llm, step_index=1)
    return _run_gated_from_draft(learning_objective, draft, draft_step, llm, use_mcp=use_mcp)


def compare_pipelines(
    learning_objective: str,
    llm: Optional[LLMClient] = None,
    use_mcp: bool = False,
) -> dict:
    """Run both pipelines on the same input and return a comparison.

    Drafts ONCE and feeds the same draft into both pipelines, so the
    comparison reflects orchestration design — not Drafter sampling
    variance. This is the key pedagogical move for the OLI module's
    agents section.

    use_mcp routes the Validator step in both pipelines through the MCP
    server, demonstrating the workflow → MCP integration. Drafter,
    Reviewer, and Reviser remain in-process LLM calls.
    """
    llm = llm or LLMClient()

    # Generate one draft, share it across both pipelines for honest comparison.
    shared_draft, shared_draft_step = drafter_agent(learning_objective, llm, step_index=1)

    naive_item, naive_trace = _run_naive_from_draft(
        learning_objective, shared_draft, shared_draft_step, llm, use_mcp=use_mcp
    )
    gated_item, gated_trace = _run_gated_from_draft(
        learning_objective, shared_draft, shared_draft_step, llm, use_mcp=use_mcp
    )

    # Re-validate both final outputs to compare quality. Use in-process here
    # regardless of use_mcp; spawning the server twice more for instrumentation
    # would be wasteful and the validator is the same either way.
    naive_val = validator_agent(naive_item, step_index=0)[0]["validation_report"]
    gated_val = validator_agent(gated_item, step_index=0)[0]["validation_report"]

    naive_flags = sum(1 for r in naive_val["results"] if r["status"] == "Flagged")
    gated_flags = sum(1 for r in gated_val["results"] if r["status"] == "Flagged")

    return {
        "learning_objective": learning_objective,
        "shared_draft": shared_draft,
        "naive": {
            "final_item": naive_item,
            "duration_seconds": naive_trace.total_duration_seconds,
            "step_count": len(naive_trace.steps),
            "final_flags": naive_flags,
            "trace_summary": naive_trace.summary(),
            "observations": naive_trace.pedagogical_observations,
        },
        "gated": {
            "final_item": gated_item,
            "duration_seconds": gated_trace.total_duration_seconds,
            "step_count": len(gated_trace.steps),
            "final_flags": gated_flags,
            "trace_summary": gated_trace.summary(),
            "observations": gated_trace.pedagogical_observations,
        },
        "comparison": {
            "speedup": (
                naive_trace.total_duration_seconds / gated_trace.total_duration_seconds
                if gated_trace.total_duration_seconds > 0
                else None
            ),
            "quality_delta": gated_flags - naive_flags,
            "summary": _comparison_summary(
                naive_trace, gated_trace, naive_flags, gated_flags
            ),
        },
    }


def _comparison_summary(
    naive: PipelineTrace,
    gated: PipelineTrace,
    naive_flags: int,
    gated_flags: int,
) -> str:
    """Generate a human-readable comparison."""
    speedup = (
        naive.total_duration_seconds / gated.total_duration_seconds
        if gated.total_duration_seconds > 0
        else 0
    )
    if naive_flags == gated_flags:
        quality_note = f"Both pipelines reached the same quality ({naive_flags} flags)."
    elif gated_flags < naive_flags:
        quality_note = (
            f"Gated produced HIGHER quality ({gated_flags} flags vs {naive_flags}) — "
            f"likely because skipping unnecessary revision avoided introducing regressions."
        )
    else:
        quality_note = (
            f"Naive produced higher quality ({naive_flags} vs {gated_flags}) — "
            f"the extra revision pass found something the gated pipeline missed."
        )

    return (
        f"Gated pipeline: {speedup:.1f}x faster ({gated.total_duration_seconds:.1f}s "
        f"vs {naive.total_duration_seconds:.1f}s). {quality_note}"
    )
