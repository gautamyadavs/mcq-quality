---
name: mcq-quality
description: Generates, audits, and revises multiple-choice questions against the 19 item-writing flaw criteria. Use when creating, reviewing, or evaluating MCQs, quiz questions, test items, or assessment items.
---

# MCQ Quality

Treat MCQ generation as assessment design and quality assurance, not writing. Every item must be valid, clear, aligned to a learning objective, and ready for human review.

## When to use this skill

Trigger on any of:

- "Generate / create / write an MCQ" or "quiz questions" or "test items"
- "Review / audit / check this MCQ"
- "Fix this question" / "make this better" applied to an item with stem + options
- "Help me assess [topic]" with implied multiple-choice format
- A learning objective followed by a request for an assessment

If the user asks for free-response, short-answer, or open-ended questions, this skill does not apply.

## Input contract

A learning objective is sufficient when it specifies BOTH:
1. What learners should be able to do (action verb).
2. The concept, skill, or decision they apply.

**Sufficient:** "Explain why retrieval practice improves long-term retention vs. rereading." / "Choose the best feedback strategy for an overconfident learner."

**Insufficient:** "Make a question about motivation." / "Assess AI ethics."

When sufficient, generate using defaults and state assumptions briefly. When insufficient, ask 1–2 clarifying questions, prioritizing:
- What should the learner be able to do with this topic?
- Who is the audience or course context?

## Defaults

Use unless overridden:
- 3 answer choices (research supports 3 plausible distractors over 4 with one weak distractor)
- 1 MCQ per request
- Difficulty, audience, Bloom's level: inferred from the learning objective
- Full review mode: draft → adversarial pre-audit → 19-IWF audit → revise if needed → final

Do not ask for difficulty, audience, count, or course context unless missing information would materially affect validity.

## Workflow: Generation

1. **Setup.** Identify the assessment target. State assumptions: audience, Bloom's level, difficulty.
2. **Verify content.** Confirm the correct answer is factually correct and distractors are factually incorrect. If unverifiable for the topic at hand, mark "Requires SME verification" in the final status regardless of audit results.
3. **Draft the MCQ.**
4. **Run deterministic pre-checks.** Execute `scripts/validate.py` against the draft. This catches surface flaws (length variance, negation words, NOTA/AOTA, absolute terms, vague qualifiers, word repeats from stem) deterministically before the LLM audit. Surface its findings.

   Treat validator output as **candidate flags, not final verdicts**. The validator detects pattern matches; you must use context to decide whether each flag is a genuine flaw or intrinsic to the topic. Example: if the stem is about "retrieval practice," the word "retrieval" will likely repeat in the correct answer — the validator flags this as #12, but if it's unavoidable given the topic, downgrade to Minor risk and note in the audit.
5. **Adversarial pre-audit.** Try to answer the draft as a test-wise learner with only partial subject knowledge. If you can eliminate options using surface features (length, specificity, grammar, repeated words), the item has cues. Note them.
6. **19-IWF audit.** Run the criterion-by-criterion audit in a Markdown table using the rubric in `references/19-iwf-rubric.md`. Read that file before producing the table — do not rely on memory of the criteria.
7. **Revision decision.** If any criterion is Minor risk or Flagged, revise. Cap at 2 revisions; if still flagged, output with status "Needs Major Revision — manual rewrite recommended."
8. **Final output** in the format specified below.

## Workflow: Review (existing item)

1. State assumptions used in the review.
2. Identify the intended learning goal. If missing and alignment cannot be judged, ask once.
3. Verify content correctness.
4. Confirm exactly one defensible best answer.
5. Check stem clarity and that the full problem is in the stem.
6. Check distractor plausibility, parallel structure, instructional value.
7. Run `scripts/validate.py` for deterministic checks.
8. Run the adversarial pass.
9. Run the 19-IWF audit against `references/19-iwf-rubric.md`.
10. If any flaw or minor risk, provide a revision and explain why it's better.
11. Output rationales, learner feedback, misconception tags, and quality status.

## 19 Item-Writing Flaws

Full definitions, examples, and per-criterion audit guidance are in `references/19-iwf-rubric.md`. Read this file at audit time. The criteria are:

1. Ambiguous wording
2. Implausible distractors
3. "None of the above"
4. Correct answer longest/most detailed
5. Gratuitous information in stem
6. True/false-style options
7. Convergence cues
8. Logical clues between options
9. "All of the above"
10. Incomplete or fill-in-the-blank stem
11. Absolute terms (always, never, all, none)
12. Word repeats from stem to correct answer
13. Unfocused stem
14. Combination / K-type options
15. Grammatical cues / non-parallel structure
16. Numerical options out of sequence
17. Vague qualifiers (often, usually, mostly)
18. More than one defensible answer
19. Negative wording (NOT, EXCEPT, LEAST)

## Audit table format

Columns: `# | Criterion | Status | Evidence | Fix if needed`

Statuses:
- **Pass**: criterion met
- **Minor risk**: a non-expert reader could be cued or confused; not a clear violation
- **Flagged**: clear violation requiring revision
- **Not applicable**: e.g., #16 on a non-numerical item

## Skepticism priorities

Watch especially for: correct answer longer or more qualified than distractors; more than one defensible option; distractors technically true but not answering the stem; distractors too obviously wrong; non-parallel options; stems testing phrasing recognition rather than the learning goal; realistic-but-unnecessary scenario detail.

## Output format: Generation

```
Assumptions used: [audience, Bloom's level, difficulty]
Assessment target: [what the item measures]

Draft MCQ:
[stem]
A) ...
B) ...
C) ...

Deterministic pre-check results:
[output of validate.py]

Adversarial pre-audit notes:
[surface cues identified, if any]

19-IWF audit:
[Markdown table]

Revision decision: [revise / accept]

Final MCQ:
[stem]
A) ...
B) ...
C) ...

Correct answer: [letter]

Instructor-facing rationales:
- Correct answer: [why correct, what it tests]
- Distractor A/B/C: [why a novice picks this, tied to a misconception]

Learner-facing feedback:
- Correct option: [see format below]
- Each incorrect option: [see format below]

Misconception tags: [2–4 short labels]

Final quality status: [Ready / Needs Minor Revision / Needs Major Revision / Reject and Rewrite / Requires SME verification]
```

## Output format: Review

```
Overall status: [one-line summary]
Assumptions used: [audience, Bloom's level, difficulty]
Learning objective alignment: [aligned / partial / misaligned]

Original MCQ: [as provided]

Deterministic pre-check results: [output of validate.py]

19-IWF audit: [table]

Recommended revision: [revised item]

Why the revision is better: [point-by-point]

Instructor-facing rationales: [as above]
Learner-facing feedback: [as below]
Misconception tags: [2–4 labels]
Final quality status: [as above]
```

## Rationale rules

- Label the correct option as "Correct answer." Only the incorrect options are labeled "Distractor A/B/C."
- Each distractor rationale explains why a novice would find it attractive AND ties it to a specific misconception, partial understanding, or suboptimal decision rule.
- No generic rationales like "This is incorrect because it is wrong."

## Learner-facing feedback format

Generate one feedback string per option for LMS delivery. This is shown to the learner on submit and is distinct from the instructor-facing rationale.

**For the correct option:**
> Correct. [1–3 sentences explaining why this is correct.]

**For each incorrect option:**
> Incorrect. [1–2 sentences explaining why this selection is wrong, tied to the underlying misconception.] The correct answer is "[exact correct option text]". [The same explanation used in the correct-option feedback above, minus the "Correct." prefix.]

Rules:
- Tone: direct, instructive, non-punitive. Do not shame the learner.
- ≤60 words per feedback string.
- Quote the correct option text verbatim from the final MCQ.
- The correct-answer explanation in incorrect feedback must match the correct-option explanation word-for-word (minus "Correct.") so learners get a consistent message regardless of which option they picked.

## Misconception tag format

2–4 short labels, 3–7 words each, describing the underlying misunderstanding.

Examples: "Confuses retrieval with rereading" / "Treats fluency as learning" / "Overweights recent feedback"

## Quality status thresholds

- **Ready**: 0 Flagged, ≤1 Minor risk
- **Needs Minor Revision**: 0 Flagged, 2+ Minor risks, or already revised once
- **Needs Major Revision**: 1+ Flagged criteria after one revision
- **Reject and Rewrite**: alignment failure, content inaccuracy, or 3+ Flagged criteria
- **Override**: items on specialized topics (high-stakes professional) carry "Requires SME verification" regardless of audit status

## Quality rules

- Prefer scenario-based stems for apply, evaluate, design, or decision-making objectives. See `references/blooms-targeting.md` for verb-to-stem-style guidance.
- Avoid trick questions.
- Avoid "all of the above," "none of the above," and negative wording (NOT/EXCEPT) unless explicitly requested.
- Make options parallel in grammar, length, specificity, and mechanism.
- Do not claim psychometric validation without student response data or IRT evidence.
- Present outputs as draft assessment materials for human review.

## Style

Direct, practical, rigorous. Clean Markdown. Tables only when they improve clarity. Do not narrate process ("Now I will run the audit..."); produce the output directly.

## Reference files

- `references/19-iwf-rubric.md` — full criterion definitions, examples, audit guidance. **Read at audit time.**
- `references/blooms-targeting.md` — Bloom's level inference from learning-objective verbs and stem-style mapping. **Read when setting up the assessment target.**
- `references/before-after-examples.md` — bad → revised MCQ pairs, one per IWF criterion. **Read when uncertain how to revise a flagged item.**
- `scripts/validate.py` — deterministic pre-check script. **Run before every audit.**
- `assets/output-schema.json` — JSON schema for structured output (for downstream LMS integration).
