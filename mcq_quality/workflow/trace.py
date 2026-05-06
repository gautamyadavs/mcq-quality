"""
trace.py — Record what each agent did so students can analyze it after.

This is the single most important pedagogical instrument in the package.
A multi-agent pipeline's failure modes are invisible if students only see
the final output. The trace surfaces:

  - Which agent produced what
  - How long each step took
  - What the agent changed vs. what was already there
  - Where revisions regressed prior fixes

Students inspect the trace to answer questions like:
  - "Did agent #3's revision actually fix the flagged criterion, or did it
     introduce a new one?"
  - "Why did the SME-style review approve an item the validator flagged?"
  - "How much wall-clock time did each agent contribute to the total?"

These are the questions the OLI module's reflection prompts will hinge on.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


@dataclass
class TraceStep:
    """One agent action in the pipeline."""
    step_index: int
    agent_name: str
    agent_role: str
    started_at: float
    duration_seconds: float
    input_summary: str           # short human-readable description of input
    output_summary: str          # short human-readable description of output
    full_input: dict             # complete structured input for analysis
    full_output: dict            # complete structured output for analysis
    notes: list[str] = field(default_factory=list)  # observations, warnings


@dataclass
class PipelineTrace:
    """Full record of one pipeline execution."""
    pipeline_name: str
    started_at: float
    finished_at: float = 0.0
    total_duration_seconds: float = 0.0
    initial_input: dict = field(default_factory=dict)
    final_output: dict = field(default_factory=dict)
    steps: list[TraceStep] = field(default_factory=list)
    pedagogical_observations: list[str] = field(default_factory=list)

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)

    def add_observation(self, observation: str) -> None:
        """Add a pedagogical observation flagged during execution.
        Examples: 'Agent 3 reviewed agent 2's output favorably without
        flagging the length cue still present.'"""
        self.pedagogical_observations.append(observation)

    def finalize(self, final_output: dict) -> None:
        self.finished_at = time.time()
        self.total_duration_seconds = self.finished_at - self.started_at
        self.final_output = final_output

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))

    def summary(self) -> str:
        """Generate a human-readable pipeline summary for inspection."""
        lines = [
            f"Pipeline: {self.pipeline_name}",
            f"Total duration: {self.total_duration_seconds:.2f}s across {len(self.steps)} steps",
            "",
        ]
        for s in self.steps:
            lines.append(
                f"  [{s.step_index}] {s.agent_name} ({s.agent_role}) — "
                f"{s.duration_seconds:.2f}s"
            )
            lines.append(f"      in:  {s.input_summary}")
            lines.append(f"      out: {s.output_summary}")
            for note in s.notes:
                lines.append(f"      note: {note}")

        if self.pedagogical_observations:
            lines.append("")
            lines.append("Pedagogical observations:")
            for obs in self.pedagogical_observations:
                lines.append(f"  • {obs}")

        return "\n".join(lines)
