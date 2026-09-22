"""Deterministic Standalone Fallback Rules for Spinal Cord Compression.

Implements accepted standalone rules:
  - SCC-ST-1: Explicit negation of cord compression -> C
  - SCC-ST-2: Hedged or equivocal cord compression -> UC
  - SCC-ST-3: Affirmed compression, pressure, displacement of the spinal cord or epidural spinal block -> S

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
CORD_ANCHOR = re.compile(
    r"\b(?:spinal\s+cord|cord|myelo\w*|spinal\s+block)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# SCC-ST-1: Explicit Negation -> C
# ------------------------------------------------------------------------------
SCC_ST1_NEGATION = re.compile(
    r"(?:"
    r"\b(?:root\s+and\s+)?cord\s+compression\s+is\s+not\s+(?:present|seen|observed|detected)\b|"
    r"\bno\s+(?:evidence\s+of\s+)?(?:spinal\s+)?cord\s+compression\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SCC-ST-2: Hedged / Equivocal / Question Mark -> UC
# ------------------------------------------------------------------------------
SCC_ST2_HEDGED = re.compile(
    r"(?:"
    r"(?:spinal\s+)?cord\s+compression\s*\?|"
    r"\(\s*(?:spinal\s+)?cord\s+compression\s*\?\s*\)|"
    r"suspicious\s+for\s+(?:spinal\s+)?cord\s+compression|"
    r"possible\s+(?:spinal\s+)?cord\s+compression"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SCC-ST-3: Affirmed Compression / Displacement of Spinal Cord -> S
# ------------------------------------------------------------------------------
SCC_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\bcompress(?:ing|ion\s+of)\s+(?:the\s+)?(?:dural\s+sac\s+and\s+)?spinal\s+cord\b|"
    r"\bspinal\s+cord\s+(?:appears\s+)?compressed\b|"
    r"\barea\s+compressed\s+by\s+the\s+[^.;\n]+,\s*(?:the\s+)?size\s+and\s+signal\s+of\s+the\s+spinal\s+cord\b|"
    r"\b(?:pressure|impingement|indentation)\s+on\s+(?:the\s+)?spinal\s+cord\b|"
    r"\bdisplacing\s+(?:the\s+)?spinal\s+cord\b|"
    r"\bpushing\s+(?:the\s+)?spinal\s+cord\b|"
    r"\bcausing\s+(?:marked\s+|significant\s+)?compression\s+of\s+(?:the\s+)?spinal\s+cord\b|"
    r"\bcausing\s+spinal\s+block\b|"
    r"\bforming\s+a\s+spinal\s+block\b"
    r")",
    re.I,
)


def evaluate_spinal_cord_compression_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Spinal cord compression."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not CORD_ANCHOR.search(clean_text):
        return None

    # 1. Hedged -> UC
    if SCC_ST2_HEDGED.search(clean_text) and not SCC_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "SCC_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "CORD_COMPRESSION_HEDGED"],
            "evidence_spans": [{"text": "hedged cord compression", "rule": "SCC-ST-2"}],
        }

    # 2. Affirmed current cord compression -> S
    if SCC_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "SCC_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "CORD_COMPRESSION_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed cord compression", "rule": "SCC-ST-3"}],
        }

    # 3. Explicit Negation -> C
    if SCC_ST1_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "SCC_ST1_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "CORD_COMPRESSION_NEGATED"],
            "evidence_spans": [{"text": "no cord compression", "rule": "SCC-ST-1"}],
        }

    return None
