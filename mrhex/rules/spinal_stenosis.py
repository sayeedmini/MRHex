"""Deterministic Standalone Fallback Rules for Spinal Stenosis.

Implements accepted standalone rules:
  - SS-ST-1: Explicit negation of spinal/canal/foraminal stenosis -> C
  - SS-ST-2: Hedged or equivocal spinal canal narrowing -> UC
  - SS-ST-3: Affirmed spinal/canal/foraminal stenosis or canal narrowing -> S

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2 (Invariant 4 preserved).
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# Anchors and Exclusions
# ------------------------------------------------------------------------------
SPINE_ANCHOR = re.compile(
    r"\b(?:cervical|thoracic|lumbar|sacral|lumbosacral|vertebra\w*|spinal\s+canal|vertebral\s+canal|cord|thecal\s+sac|dural\s+sac)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# SS-ST-1: Explicit Negation -> C
# ------------------------------------------------------------------------------
SS_ST1_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:significant\s+)?(?:spinal\s+canal|central\s+canal|canal|foraminal)?\s*stenosis\b|"
    r"\b(?:spinal\s+canal|canal|foraminal)\s+stenosis\s+is\s+not\s+(?:seen|observed|detected)\b|"
    r"\bthe\s+central\s+spinal\s+canal\s+is\s+wide\b|"
    r"\bwidening\s+of\s+the\s+central\s+spinal\s+canal\b|"
    r"\bno\s+significant\s+protrusion\s+towards\s+the\s+canal\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SS-ST-2: Hedged / Equivocal / Question Mark -> UC
# ------------------------------------------------------------------------------
SS_ST2_HEDGED = re.compile(
    r"(?:"
    r"(?:spinal\s+canal\s+|canal\s+|spinal\s+)?stenosis\s*\?|"
    r"\(\s*(?:spinal\s+canal\s+|canal\s+|spinal\s+)?stenosis\s*\?\s*\)|"
    r"probable\s+(?:spinal\s+canal|canal)\s+stenosis|"
    r"suspicious\s+for\s+(?:spinal\s+canal|canal)\s+stenosis"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SS-ST-3: Affirmed Spinal / Canal / Foraminal Stenosis -> S
# ------------------------------------------------------------------------------
SS_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:cervical|thoracic|lumbar|lumbosacral|spinal|central|canal|neural|bilateral|unilateral|left|right)?\s*foraminal\s+stenosis\b|"
    r"\b(?:cervical|thoracic|lumbar|lumbosacral|spinal|central|vertebral)?\s*canal\s+stenosis\b|"
    r"\b(?:cervical|thoracic|lumbar|spinal)\s+stenosis\b|"
    r"\bspondylosis(?:-stenosis|\s+and\s+stenosis)\b|"
    r"\b(?:the\s+)?(?:spinal|vertebral)\s+canal\s+is\s+(?:markedly\s+|significantly\s+|moderately\s+)?narrowed\b|"
    r"\bnarrow(?:ed)?\s+spinal\s+canal\b|"
    r"\bnarrowing\s+of\s+(?:the\s+)?(?:anteroposterior\s+diameter\s+of\s+the\s+)?(?:vertebral|spinal)\s+canal\b|"
    r"\bcausing\s+dural\s+sac\s+compression\b|"
    r"\bcompressing\s+(?:the\s+)?dural\s+sac\b|"
    r"\bextension\s+of\s+disc-osteophyte\s+complexes\s+to\s+the\s+spinal\s+canal\b"
    r")",
    re.I,
)


SS_SENTENCE_NEGATION = re.compile(
    r"\b(?:not\s+(?:seen|observed|detected|present)|no\s+(?:evidence\s+of\s+)?|without\s+)\b",
    re.I,
)


def evaluate_spinal_stenosis_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Spinal stenosis."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not SPINE_ANCHOR.search(clean_text):
        return None

    # Check for affirmative stenosis in non-negated context
    has_non_negated_affirmative = False
    for sent in re.split(r"[.\n;]", clean_text):
        sent = sent.strip()
        if not sent:
            continue
        if SS_ST3_AFFIRMATIVE.search(sent) and not SS_SENTENCE_NEGATION.search(sent):
            has_non_negated_affirmative = True
            break

    # 1. Hedged / question-marked -> UC
    if SS_ST2_HEDGED.search(clean_text) and not has_non_negated_affirmative:
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "SS_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "SPINAL_STENOSIS_HEDGED"],
            "evidence_spans": [{"text": "hedged spinal stenosis", "rule": "SS-ST-2"}],
        }

    # 2. Affirmed current stenosis -> S (Affirmative takes precedence if definite stenosis is documented at any level)
    if has_non_negated_affirmative:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "SS_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "SPINAL_STENOSIS_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed spinal stenosis", "rule": "SS-ST-3"}],
        }

    # 3. Explicit Negation -> C
    if SS_ST1_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "SS_ST1_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "SPINAL_STENOSIS_NEGATED"],
            "evidence_spans": [{"text": "no spinal stenosis", "rule": "SS-ST-1"}],
        }

    return None
