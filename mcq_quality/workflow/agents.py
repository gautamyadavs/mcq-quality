"""
agents.py — The four agents in the MCQ quality pipeline.

Each agent has:
  - A distinct role (drafter, validator, reviewer, reviser)
  - A specific system prompt
  - A defined input/output contract

The Validator Agent is special: it does NOT use the LLM. It runs the
deterministic Python validator from the MCP server. This is intentional —
it shows students that "agent" doesn't have to mean "LLM call." A
deterministic tool wrapped in the agent interface is often the right
choice for one of the steps.

The Reviewer and Reviser are LLM-based. The Reviewer uses a pedagogical
rubric (alignment, scenario-realism, cognitive level). The Reviser uses
a writing-quality rubric (parallelism, clarity, distractor plausibility).
The two rubrics are intentionally different so the agents have something
to disagree about — a single-rubric review is just sycophancy.
"""

import time
from typing import Any

from .llm_client import LLMClient
from .trace import TraceStep


# ---------- Agent 1: Drafter ----------

DRAFTER_SYSTEM = """You are an MCQ Drafter for educational assessment.

Given a learning objective, draft a single high-quality multiple-choice question
with 4 options (one correct, three plausible distractors).

Output ONLY a JSON object with this exact structure:
{
  "stem": "...",
  "options": ["A option text", "B option text", "C option text", "D option text"],
  "correct_index": 0,
  "blooms_level": "Remember|Understand|Apply|Analyze|Evaluate|Create",
  "rationale": "Brief note on why this question fits the learning objective."
}

Make options parallel in length, grammar, and specificity. Avoid 'all of the above'
and 'none of the above'. Use a scenario stem for Apply-level or higher objectives."""


def drafter_agent(
    learning_objective: str,
    llm: LLMClient,
    step_index: int,
) -> tuple[dict, TraceStep]:
    """Draft an MCQ from a learning objective."""
    started = time.time()
    user_msg = f"Learning objective: {learning_objective}\n\nDraft one MCQ."
    output = llm.complete_json(DRAFTER_SYSTEM, user_msg)

    step = TraceStep(
        step_index=step_index,
        agent_name="Drafter",
        agent_role="LLM-based: produces initial item from learning objective",
        started_at=started,
        duration_seconds=time.time() - started,
        input_summary=f"LO: {learning_objective[:80]}",
        output_summary=f"Drafted {output.get('blooms_level', '?')}-level item: {output.get('stem', '')[:60]}...",
        full_input={"learning_objective": learning_objective},
        full_output=output,
    )
    return output, step


# ---------- Agent 2: Validator (deterministic) ----------

def validator_agent(
    item: dict,
    step_index: int,
) -> tuple[dict, TraceStep]:
    """Run the deterministic IWF validator. NO LLM CALL."""
    started = time.time()

    # Validator step uses the shared core function. This is the same
    # validate_item that the skill's script and the MCP server's tool both
    # call into; keeping the import here means there's exactly one place where
    # the IWF rules live.
    #
    # When compare_pipelines is run with --use-mcp, the workflow uses
    # validator_agent_via_mcp instead of this function, demonstrating the
    # workflow → MCP integration. Both agents return the same report shape.
    from mcq_quality.core import run_validator

    report = run_validator(
        stem=item["stem"],
        options=item["options"],
        correct_index=item["correct_index"],
    )

    flagged = [r for r in report["results"] if r["status"] == "Flagged"]
    minor = [r for r in report["results"] if r["status"] == "Minor risk"]

    notes = []
    if flagged:
        notes.append(
            f"Deterministic flags: criteria {[r['criterion'] for r in flagged]}"
        )
    if minor:
        notes.append(
            f"Minor risks: criteria {[r['criterion'] for r in minor]}"
        )

    step = TraceStep(
        step_index=step_index,
        agent_name="Validator",
        agent_role="Deterministic Python: runs 19-IWF rule-based checks (no LLM)",
        started_at=started,
        duration_seconds=time.time() - started,
        input_summary=f"Item: {item['stem'][:60]}...",
        output_summary=f"{len(flagged)} flagged, {len(minor)} minor risks",
        full_input={"item": item},
        full_output={"validation_report": report},
        notes=notes,
    )
    return {"validation_report": report}, step


# ---------- Agent 2 (alternative): Validator via MCP ----------

def validator_agent_via_mcp(
    item: dict,
    step_index: int,
) -> tuple[dict, TraceStep]:
    """
    Same role as validator_agent, but routes the validator call through the
    MCP server instead of importing core directly.

    Selected when compare_pipelines is run with --use-mcp. Demonstrates the
    workflow → MCP integration: the workflow becomes an MCP client, spawns
    the mcq-quality server as a subprocess, and calls validate_mcq through
    the protocol.

    Returns the same report shape as validator_agent, so downstream agents
    (Reviewer, Reviser) don't need to know which path produced it.
    """
    from .mcp_client import call_validate_mcq_sync

    started = time.time()
    report = call_validate_mcq_sync(
        stem=item["stem"],
        options=item["options"],
        correct_index=item["correct_index"],
    )

    flagged = [r for r in report["results"] if r["status"] == "Flagged"]
    minor = [r for r in report["results"] if r["status"] == "Minor risk"]

    notes = ["Routed through MCP server (validate_mcq tool)"]
    if flagged:
        notes.append(
            f"Deterministic flags: criteria {[r['criterion'] for r in flagged]}"
        )
    if minor:
        notes.append(
            f"Minor risks: criteria {[r['criterion'] for r in minor]}"
        )

    step = TraceStep(
        step_index=step_index,
        agent_name="Validator (via MCP)",
        agent_role="Workflow calls the mcq-quality MCP server's validate_mcq tool",
        started_at=started,
        duration_seconds=time.time() - started,
        input_summary=f"Item: {item['stem'][:60]}...",
        output_summary=f"{len(flagged)} flagged, {len(minor)} minor risks (via MCP)",
        full_input={"item": item, "transport": "mcp"},
        full_output={"validation_report": report, "transport": "mcp"},
        notes=notes,
    )
    return {"validation_report": report}, step


# ---------- Agent 3: Pedagogical Reviewer ----------

REVIEWER_SYSTEM = """You are a Pedagogical Reviewer for assessment items.

Your job is to evaluate whether an MCQ is pedagogically sound — NOT whether
it is well-written (that is the Reviser's job).

Evaluate ONLY these three dimensions:
  1. Alignment: Does the item assess the stated learning objective?
  2. Cognitive level: Does the item match the claimed Bloom's level?
  3. Scenario quality: For Apply+ items, is the scenario realistic and necessary?

Output ONLY JSON:
{
  "alignment": {"verdict": "aligned|partial|misaligned", "reasoning": "..."},
  "cognitive_level": {"verdict": "matches|too_low|too_high", "reasoning": "..."},
  "scenario_quality": {"verdict": "good|weak|n/a", "reasoning": "..."},
  "overall": "approve|revise|reject",
  "concerns": ["list", "of", "specific", "concerns"]
}

Be honest. If the item passes, say so clearly. If it has problems, name them
specifically with quoted text from the item."""


def reviewer_agent(
    item: dict,
    learning_objective: str,
    validation_report: dict,
    llm: LLMClient,
    step_index: int,
) -> tuple[dict, TraceStep]:
    """Pedagogical review focused on alignment, cognitive level, scenario."""
    started = time.time()

    # Note: we do NOT pass the validation report into the prompt. The
    # reviewer's job is pedagogical, not duplicating the validator's work.
    # Keeping rubrics separate is what makes multi-agent review honest.

    user_msg = (
        f"Learning objective: {learning_objective}\n\n"
        f"Item to review:\n"
        f"Stem: {item['stem']}\n"
        f"Options:\n"
        + "\n".join(
            f"  {chr(65+i)}) {opt}"
            for i, opt in enumerate(item["options"])
        )
        + f"\nCorrect: {chr(65 + item['correct_index'])}\n"
        f"Claimed Bloom's: {item.get('blooms_level', '?')}\n\n"
        f"Review for pedagogical quality only."
    )

    output = llm.complete_json(REVIEWER_SYSTEM, user_msg)

    notes = []
    if output.get("overall") == "approve" and validation_report.get("results"):
        flagged = [r for r in validation_report["results"] if r["status"] == "Flagged"]
        if flagged:
            notes.append(
                f"PEDAGOGICAL OBSERVATION: Reviewer approved despite "
                f"{len(flagged)} validator-flagged criteria still present "
                f"(criteria {[f['criterion'] for f in flagged]}). This is the "
                f"sycophancy/disagreement issue the OLI module discusses — "
                f"reviewer rubric and validator rubric don't overlap, so each "
                f"can independently approve while the item still has flaws."
            )

    step = TraceStep(
        step_index=step_index,
        agent_name="Reviewer",
        agent_role="LLM-based: pedagogical review (alignment, cognitive level, scenario)",
        started_at=started,
        duration_seconds=time.time() - started,
        input_summary=f"Item + LO; pedagogical rubric only",
        output_summary=f"Verdict: {output.get('overall', '?')}, concerns: {len(output.get('concerns', []))}",
        full_input={"item": item, "learning_objective": learning_objective},
        full_output=output,
        notes=notes,
    )
    return output, step


# ---------- Agent 4: Reviser ----------

REVISER_SYSTEM = """You are an MCQ Reviser. You take a draft item plus feedback
from a deterministic validator and a pedagogical reviewer, and produce a revised
version that addresses the issues raised.

CRITICAL: When you revise to fix one issue, do NOT introduce new issues. Common
mistakes to avoid:
  - Lengthening the correct answer (introduces length cue)
  - Adding stem words to the correct answer (introduces word repeat)
  - Making distractors implausible (introduces #2)
  - Replacing one absolute term with another

Output ONLY JSON with the revised item in the same format as the draft:
{
  "stem": "...",
  "options": ["...", "...", "...", "..."],
  "correct_index": N,
  "blooms_level": "...",
  "rationale": "...",
  "revision_notes": "what you changed and why"
}"""


def reviser_agent(
    item: dict,
    validation_report: dict,
    review_output: dict,
    llm: LLMClient,
    step_index: int,
) -> tuple[dict, TraceStep]:
    """Revise the item based on validator + reviewer feedback."""
    started = time.time()

    flagged = [r for r in validation_report["results"] if r["status"] == "Flagged"]
    minor = [r for r in validation_report["results"] if r["status"] == "Minor risk"]
    flagged_summary = (
        "\n".join(f"  - Criterion #{r['criterion']}: {r['evidence']}" for r in flagged + minor)
        or "  (none)"
    )

    review_concerns = review_output.get("concerns", [])
    review_summary = "\n".join(f"  - {c}" for c in review_concerns) or "  (none)"

    user_msg = (
        f"Original item:\n"
        f"Stem: {item['stem']}\n"
        f"Options:\n"
        + "\n".join(
            f"  {chr(65+i)}) {opt}"
            for i, opt in enumerate(item["options"])
        )
        + f"\nCorrect: {chr(65 + item['correct_index'])}\n\n"
        f"Validator findings:\n{flagged_summary}\n\n"
        f"Reviewer concerns:\n{review_summary}\n\n"
        f"Produce a revised item that addresses all of the above without introducing new flaws."
    )

    output = llm.complete_json(REVISER_SYSTEM, user_msg)

    step = TraceStep(
        step_index=step_index,
        agent_name="Reviser",
        agent_role="LLM-based: revises item based on validator + reviewer feedback",
        started_at=started,
        duration_seconds=time.time() - started,
        input_summary=f"Original + {len(flagged)} flags + {len(review_concerns)} concerns",
        output_summary=f"Revised: {output.get('stem', '')[:60]}...",
        full_input={
            "original_item": item,
            "validation_report": validation_report,
            "review_output": review_output,
        },
        full_output=output,
    )
    return output, step
