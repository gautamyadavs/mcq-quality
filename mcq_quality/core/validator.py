#!/usr/bin/env python3
"""
validate.py — Deterministic pre-checks for the 19 item-writing flaws.

Run this BEFORE the LLM audit. It catches the IWFs that can be detected
by rules alone, freeing the LLM critique to focus on the harder semantic
flaws (#1 ambiguity, #2 plausibility, #7 convergence, #13 unfocused stem,
#18 multiple defensible answers).

Usage:
    python validate.py < item.json
    python validate.py item.json
    python validate.py --stdin

Input JSON schema:
    {
        "stem": "string — the question stem",
        "options": ["string", "string", ...],
        "correct_index": 0  // 0-based index of correct option
    }

Output: JSON report with one entry per checkable IWF criterion.
"""

import json
import re
import sys
from typing import Optional


# Criteria covered deterministically. Others (1, 2, 5, 7, 8, 13, 18) are
# semantic and left to the LLM audit.
DETERMINISTIC_CRITERIA = [3, 4, 6, 9, 10, 11, 12, 14, 15, 16, 17, 19]


def check_3_none_of_above(options: list[str]) -> dict:
    """IWF #3: 'None of the above' detection."""
    pattern = re.compile(r"\bnone of (the )?above\b", re.IGNORECASE)
    matches = [i for i, opt in enumerate(options) if pattern.search(opt)]
    return {
        "criterion": 3,
        "name": "None of the above",
        "status": "Flagged" if matches else "Pass",
        "evidence": f"NOTA appears in option(s) {matches}" if matches else "No NOTA detected",
    }


def check_4_length_cue(options: list[str], correct_index: int) -> dict:
    """IWF #4: Correct answer noticeably longer than distractors."""
    if not options or correct_index >= len(options):
        return {"criterion": 4, "name": "Length cue", "status": "Not applicable", "evidence": "Invalid input"}

    correct_len = len(options[correct_index])
    distractor_lens = [len(opt) for i, opt in enumerate(options) if i != correct_index]
    if not distractor_lens:
        return {"criterion": 4, "name": "Length cue", "status": "Not applicable", "evidence": "No distractors"}

    avg_distractor = sum(distractor_lens) / len(distractor_lens)
    if avg_distractor == 0:
        return {"criterion": 4, "name": "Length cue", "status": "Not applicable", "evidence": "Zero-length distractors"}

    ratio = correct_len / avg_distractor

    if ratio >= 1.5:
        status = "Flagged"
        evidence = f"Correct answer is {ratio:.2f}x average distractor length ({correct_len} vs {avg_distractor:.0f} chars)"
    elif ratio >= 1.25:
        status = "Minor risk"
        evidence = f"Correct answer is {ratio:.2f}x average distractor length"
    else:
        status = "Pass"
        evidence = f"Correct answer length ratio: {ratio:.2f}x"

    return {"criterion": 4, "name": "Length cue", "status": status, "evidence": evidence}


def check_6_truefalse_options(options: list[str]) -> dict:
    """IWF #6: True/false-style independent declarative options."""
    # Heuristic: options ending in periods AND containing finite verbs are likely declarative.
    # Combined with options that don't share a common grammatical completion of a stem.
    period_count = sum(1 for opt in options if opt.strip().endswith("."))
    long_count = sum(1 for opt in options if len(opt.split()) >= 8)

    if period_count >= len(options) * 0.75 and long_count >= len(options) * 0.5:
        return {
            "criterion": 6,
            "name": "True/false-style options",
            "status": "Minor risk",
            "evidence": f"{period_count}/{len(options)} options end in periods and {long_count} are long-form; check for parallel structure",
        }
    return {"criterion": 6, "name": "True/false-style options", "status": "Pass", "evidence": "Options appear to be parallel completions"}


def check_9_all_of_above(options: list[str]) -> dict:
    """IWF #9: 'All of the above' detection."""
    pattern = re.compile(r"\ball of (the )?above\b", re.IGNORECASE)
    matches = [i for i, opt in enumerate(options) if pattern.search(opt)]
    return {
        "criterion": 9,
        "name": "All of the above",
        "status": "Flagged" if matches else "Pass",
        "evidence": f"AOTA appears in option(s) {matches}" if matches else "No AOTA detected",
    }


def check_10_incomplete_stem(stem: str) -> dict:
    """IWF #10: Fill-in-the-blank or incomplete stem."""
    stripped = stem.rstrip()
    has_blank = bool(re.search(r"_{2,}", stripped))
    ends_with_question = stripped.endswith("?") or stripped.endswith(":")
    ends_with_period = stripped.endswith(".")
    ends_with_directive = bool(re.search(r"(which|what|how|why|when|where|select|choose|identify)\b.*[.?:]?\s*$", stripped, re.IGNORECASE))

    if has_blank:
        return {"criterion": 10, "name": "Incomplete stem", "status": "Flagged", "evidence": "Stem contains fill-in blank (___)"}
    if not (ends_with_question or ends_with_period) and not ends_with_directive:
        return {"criterion": 10, "name": "Incomplete stem", "status": "Minor risk", "evidence": "Stem does not end in a question mark, period, or clear directive"}
    return {"criterion": 10, "name": "Incomplete stem", "status": "Pass", "evidence": "Stem appears complete"}


def check_11_absolutes(options: list[str]) -> dict:
    """IWF #11: Absolute terms (always, never, all, none, every)."""
    absolutes = ["always", "never", "all", "none", "every", "must", "no one", "everyone"]
    pattern = re.compile(r"\b(" + "|".join(absolutes) + r")\b", re.IGNORECASE)

    flagged_options = []
    for i, opt in enumerate(options):
        if pattern.search(opt):
            flagged_options.append(i)

    if len(flagged_options) >= 2:
        return {
            "criterion": 11,
            "name": "Absolute terms",
            "status": "Flagged",
            "evidence": f"Absolutes detected in options {flagged_options}",
        }
    if len(flagged_options) == 1:
        return {
            "criterion": 11,
            "name": "Absolute terms",
            "status": "Minor risk",
            "evidence": f"Absolute term in option {flagged_options[0]} — verify it's defensible",
        }
    return {"criterion": 11, "name": "Absolute terms", "status": "Pass", "evidence": "No absolute terms"}


def _tokenize(text: str) -> set[str]:
    """Lowercase content-word tokenization, stripped of stop words."""
    stop = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "of", "in", "on", "at", "to", "for", "with", "by", "from", "about",
        "and", "or", "but", "not", "as", "if", "then", "than", "that", "this",
        "these", "those", "it", "its", "his", "her", "their", "our", "your",
        "which", "what", "how", "why", "when", "where", "who", "whom",
        "do", "does", "did", "have", "has", "had", "can", "could", "should",
        "would", "will", "may", "might", "best", "most", "more", "less",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {w for w in words if w not in stop}


def check_12_word_repeat(stem: str, options: list[str], correct_index: int) -> dict:
    """IWF #12: Distinctive word from stem appears only in correct answer."""
    if correct_index >= len(options):
        return {"criterion": 12, "name": "Word repeat from stem", "status": "Not applicable", "evidence": "Invalid input"}

    stem_words = _tokenize(stem)
    correct_words = _tokenize(options[correct_index])
    distractor_words = set()
    for i, opt in enumerate(options):
        if i != correct_index:
            distractor_words |= _tokenize(opt)

    # Words that appear in stem AND correct answer but NOT in any distractor
    cuing_words = stem_words & correct_words - distractor_words

    if cuing_words:
        return {
            "criterion": 12,
            "name": "Word repeat from stem",
            "status": "Flagged",
            "evidence": f"Word(s) {sorted(cuing_words)} appear in stem and correct answer but no distractor",
        }
    return {"criterion": 12, "name": "Word repeat from stem", "status": "Pass", "evidence": "No cuing word repeats detected"}


def check_14_ktype(options: list[str]) -> dict:
    """IWF #14: K-type combination options ('A and B only', 'all of A, B, C')."""
    patterns = [
        re.compile(r"\b(only|both|all of)\b.*\b(and|,)\b", re.IGNORECASE),
        re.compile(r"\b[A-D]\s+and\s+[A-D]\b", re.IGNORECASE),
        re.compile(r"\b(option|options)\s+[A-D]", re.IGNORECASE),
    ]
    flagged = []
    for i, opt in enumerate(options):
        for p in patterns:
            if p.search(opt):
                flagged.append(i)
                break

    if flagged:
        return {
            "criterion": 14,
            "name": "K-type options",
            "status": "Flagged",
            "evidence": f"K-type combination structure in option(s) {flagged}",
        }
    return {"criterion": 14, "name": "K-type options", "status": "Pass", "evidence": "No K-type combination options"}


def check_15_grammatical_cue(stem: str, options: list[str]) -> dict:
    """IWF #15: Article cue ('a' vs 'an') or part-of-speech mismatch."""
    # Article cue check: stem ends with 'a' or 'an' indefinite article
    stripped = stem.rstrip().rstrip(":.")
    article_match = re.search(r"\b(an?)\s*$", stripped, re.IGNORECASE)

    if article_match:
        article = article_match.group(1).lower()
        # Check which options fit grammatically
        vowel_start = re.compile(r"^[aeiouAEIOU]")
        consonant_start = re.compile(r"^[^aeiouAEIOU\s]")
        vowel_options = [i for i, opt in enumerate(options) if vowel_start.match(opt.strip())]
        consonant_options = [i for i, opt in enumerate(options) if consonant_start.match(opt.strip())]

        if article == "an" and len(vowel_options) < len(options) and len(vowel_options) > 0:
            return {
                "criterion": 15,
                "name": "Grammatical cue",
                "status": "Flagged",
                "evidence": f"Stem ends with 'an'; only options {vowel_options} start with vowels",
            }
        if article == "a" and len(consonant_options) < len(options) and len(consonant_options) > 0:
            return {
                "criterion": 15,
                "name": "Grammatical cue",
                "status": "Flagged",
                "evidence": f"Stem ends with 'a'; only options {consonant_options} start with consonants",
            }

    # Parallel structure check: do options share grammatical opening?
    first_words = []
    for opt in options:
        m = re.match(r"^\s*(\w+)", opt)
        if m:
            first_words.append(m.group(1).lower())

    # Crude: check if first words are all same POS class by suffix heuristic
    suffixes = {
        "ing": "gerund/participle",
        "ed": "past/participle",
        "tion": "noun",
        "ment": "noun",
        "ness": "noun",
        "ity": "noun",
    }
    classes = []
    for w in first_words:
        cls = "other"
        for suf, name in suffixes.items():
            if w.endswith(suf):
                cls = name
                break
        classes.append(cls)

    if len(set(classes)) >= 4:
        return {
            "criterion": 15,
            "name": "Grammatical cue",
            "status": "Minor risk",
            "evidence": f"Options begin with mixed grammatical classes: {classes} — verify parallel structure",
        }

    return {"criterion": 15, "name": "Grammatical cue", "status": "Pass", "evidence": "No obvious grammatical cue"}


def check_16_numerical_order(options: list[str]) -> dict:
    """IWF #16: Numerical options out of sequential order."""
    # Extract leading numerical value from each option (ignoring NOTA/AOTA)
    nota_pattern = re.compile(r"\b(none|all) of (the )?above\b", re.IGNORECASE)
    numbers = []
    for opt in options:
        if nota_pattern.search(opt):
            continue  # skip NOTA/AOTA — not a numerical comparison candidate
        m = re.match(r"^\s*([\d,]+(?:\.\d+)?)", opt)
        if m:
            try:
                numbers.append(float(m.group(1).replace(",", "")))
            except ValueError:
                return {"criterion": 16, "name": "Numerical order", "status": "Not applicable", "evidence": "Mixed numerical and non-numerical options"}
        else:
            return {"criterion": 16, "name": "Numerical order", "status": "Not applicable", "evidence": "Not all options are numerical"}

    if len(numbers) < 2:
        return {"criterion": 16, "name": "Numerical order", "status": "Not applicable", "evidence": "Fewer than 2 numerical options"}

    is_ascending = all(numbers[i] <= numbers[i + 1] for i in range(len(numbers) - 1))
    is_descending = all(numbers[i] >= numbers[i + 1] for i in range(len(numbers) - 1))

    if is_ascending or is_descending:
        return {"criterion": 16, "name": "Numerical order", "status": "Pass", "evidence": f"Numbers in {'ascending' if is_ascending else 'descending'} order"}
    return {
        "criterion": 16,
        "name": "Numerical order",
        "status": "Flagged",
        "evidence": f"Numerical options out of monotonic order: {numbers}",
    }


def check_17_vague_qualifiers(options: list[str], correct_index: int) -> dict:
    """IWF #17: Vague qualifiers (often, usually, mostly, frequently, generally)."""
    qualifiers = ["often", "usually", "mostly", "frequently", "generally", "sometimes", "tends to", "typically"]
    pattern = re.compile(r"\b(" + "|".join(qualifiers) + r")\b", re.IGNORECASE)

    correct_has = bool(pattern.search(options[correct_index])) if correct_index < len(options) else False
    distractors_have = [i for i, opt in enumerate(options) if i != correct_index and pattern.search(opt)]

    if correct_has and not distractors_have:
        return {
            "criterion": 17,
            "name": "Vague qualifiers",
            "status": "Flagged",
            "evidence": "Vague qualifier appears only in correct answer (cuing risk)",
        }
    if correct_has or distractors_have:
        return {
            "criterion": 17,
            "name": "Vague qualifiers",
            "status": "Minor risk",
            "evidence": f"Vague qualifiers present; correct={correct_has}, distractors={distractors_have}. Verify distribution doesn't cue answer.",
        }
    return {"criterion": 17, "name": "Vague qualifiers", "status": "Pass", "evidence": "No vague qualifiers"}


def check_19_negative_wording(stem: str) -> dict:
    """IWF #19: Negative wording (NOT, EXCEPT, LEAST) without typographic emphasis."""
    # Check for unmarked negatives (lowercase or plain)
    unmarked = re.search(r"\b(not|except|least)\b", stem)
    marked = re.search(r"\b(NOT|EXCEPT|LEAST)\b", stem) or "**not**" in stem.lower() or "*not*" in stem.lower()

    if unmarked and not marked:
        return {
            "criterion": 19,
            "name": "Negative wording",
            "status": "Flagged",
            "evidence": f"Unmarked negative '{unmarked.group()}' in stem",
        }
    if marked:
        return {
            "criterion": 19,
            "name": "Negative wording",
            "status": "Minor risk",
            "evidence": "Negative wording present with emphasis — verify safety-critical or explicit user request",
        }
    return {"criterion": 19, "name": "Negative wording", "status": "Pass", "evidence": "Stem is positively worded"}


def validate_item(item: dict) -> dict:
    """Run all deterministic checks on an MCQ item."""
    stem = item.get("stem", "")
    options = item.get("options", [])
    correct_index = item.get("correct_index", 0)

    if not stem or not options:
        return {"error": "Missing stem or options", "results": []}

    results = [
        check_3_none_of_above(options),
        check_4_length_cue(options, correct_index),
        check_6_truefalse_options(options),
        check_9_all_of_above(options),
        check_10_incomplete_stem(stem),
        check_11_absolutes(options),
        check_12_word_repeat(stem, options, correct_index),
        check_14_ktype(options),
        check_15_grammatical_cue(stem, options),
        check_16_numerical_order(options),
        check_17_vague_qualifiers(options, correct_index),
        check_19_negative_wording(stem),
    ]

    flagged = [r for r in results if r["status"] == "Flagged"]
    minor = [r for r in results if r["status"] == "Minor risk"]

    return {
        "summary": {
            "flagged_count": len(flagged),
            "minor_risk_count": len(minor),
            "deterministic_criteria_checked": len(DETERMINISTIC_CRITERIA),
            "semantic_criteria_remaining": [1, 2, 5, 7, 8, 13, 18],
            "note": "Criteria 1, 2, 5, 7, 8, 13, and 18 require LLM-based semantic evaluation in the next audit step.",
        },
        "results": results,
    }


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--stdin":
        with open(sys.argv[1]) as f:
            item = json.load(f)
    else:
        item = json.load(sys.stdin)

    report = validate_item(item)
    print(json.dumps(report, indent=2))


# ============================================================
# Function-call API for the skill, MCP server, and workflow to share
# ============================================================
# validate_item() above is the core validator. The two functions below wrap it
# in a slightly cleaner function-call shape that the skill scripts, MCP server
# tools, and workflow agents all use. Keeping them in this file (rather than a
# separate helper module) is deliberate: there's exactly one place where
# validation logic lives, and all three layers reuse it.

def run_validator(stem: str, options: list[str], correct_index: int) -> dict:
    """
    Run the deterministic IWF validator on an item.

    Returns the same structure validate_item produces:
    {
        "summary": {"flagged_count", "minor_risk_count", ...},
        "results": [{"criterion", "name", "status", "evidence"}, ...]
    }
    """
    return validate_item({
        "stem": stem,
        "options": options,
        "correct_index": correct_index,
    })


def summarize_validation(report: dict) -> str:
    """Produce a one-line human-readable summary of validator output."""
    s = report.get("summary", {})
    flagged = s.get("flagged_count", 0)
    minor = s.get("minor_risk_count", 0)
    if flagged == 0 and minor == 0:
        return "Clean: no deterministic IWF issues detected."
    parts = []
    if flagged:
        parts.append(f"{flagged} flagged")
    if minor:
        parts.append(f"{minor} minor risk{'s' if minor != 1 else ''}")
    return f"{', '.join(parts)}. See results array for details."


if __name__ == "__main__":
    main()
