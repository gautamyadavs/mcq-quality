# Bloom's Targeting Guide

Used at the Setup step to infer Bloom's level from the learning objective and choose an appropriate stem style.

## Verb-to-level mapping

| Bloom's Level | Common LO verbs | What the item should test |
|---|---|---|
| Remember | define, list, recall, name, identify, label | Recognition or recall of facts, terms, definitions |
| Understand | explain, describe, summarize, classify, compare, interpret | Translation between forms or restatement of meaning |
| Apply | apply, use, demonstrate, calculate, implement, choose, solve | Use of a procedure or principle in a new situation |
| Analyze | analyze, distinguish, differentiate, organize, attribute, deconstruct | Breaking material into parts and detecting relationships |
| Evaluate | evaluate, judge, critique, justify, defend, assess, recommend | Making judgments based on criteria |
| Create | design, construct, plan, produce, formulate, devise | Putting elements together to form a coherent whole |

## Verbs that mislead

Watch for these — they sound like one level but often imply another:

- **"Understand"** as a verb is too vague to map cleanly. Look at the rest of the objective for what the learner does with the understanding.
- **"Know"** is not a Bloom's verb. Treat as Remember unless context indicates otherwise.
- **"Choose"** and **"select"** look like Remember but usually imply Apply when the choice involves applying a principle to a scenario.
- **"Identify"** is Remember when picking from a list of facts but Analyze when picking out a feature embedded in a complex stimulus.
- **"Compare"** is Understand when contrasting two known concepts but Analyze when the learner must derive the comparison framework themselves.

## Stem style by level

### Remember / Understand

Direct question stems work well. Scenarios are usually unnecessary and add reading load.

> Which best describes the function of working memory?

### Apply / Analyze / Evaluate / Create

Scenario-based stems are strongly preferred. The scenario gives the learner a context in which to apply the principle, making the cognitive demand authentic rather than recognition-based.

> A learner reports feeling "completely ready" for an exam after rereading their notes three times. What is the most effective next step for the instructor?

A scenario-based stem at Apply or higher should:
- Place the learner in a realistic decision point.
- Provide only details that affect the answer (no gratuitous detail — see IWF #5).
- Pose a clear question or directive at the end.

## Difficulty calibration

Bloom's level and difficulty are related but distinct.

- A Remember-level item can be hard if the fact is obscure.
- An Apply-level item can be easy if the scenario is heavily scaffolded.

When inferring difficulty, consider:
- How many steps of reasoning between stem and answer.
- How much domain knowledge the learner needs beyond the stem itself.
- How plausible the distractors are (more plausible = harder).

Default to "moderate" difficulty unless the LO uses qualifiers like "introductory," "basic," "advanced," or "expert."

## When the learning objective verb conflicts with the requested level

If the user explicitly requests an Apply-level item but the LO is written at Remember ("Define X"), surface the mismatch in the Assumptions block:

> Assumptions: LO is written at Remember ("Define"), but requested level is Apply. I'll generate at Apply by adding a scenario in which the learner applies the definition. Confirm if you wanted a Remember-level item instead.

Do not silently rewrite the LO. Surface the choice.
