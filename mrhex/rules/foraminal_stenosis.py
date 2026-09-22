"""Pathology-specific standalone fallback rules for Foraminal Spinal Stenosis (Batch 11).

Target pathology: 'Foraminal Spinal Stenosis'

Handles:
- Explicit whole-foraminal negation (e.g. 'no foraminal stenosis', 'foramina are patent') -> C
- Equivocal / hedged foraminal stenosis ('questionable foraminal narrowing', '?') -> UC
- Direct affirmative foraminal narrowing / stenosis ('narrowing the right neural foramen',
  'neural foraminal stenosis', 'disk protrusion narrowing neural foramen') -> S
"""
import re
from typing import Optional, Dict, Any

# Negation patterns
FSS_NEGATION_PATTERNS = [
    re.compile(r"\bno\s+(?:significant\s+|marked\s+)?(?:neural\s+|intervertebral\s+)?foraminal\s+(?:stenosis|narrowing|encroachment|compromise)\b", re.I),
    re.compile(r"\bwithout\s+(?:significant\s+)?(?:neural\s+|intervertebral\s+)?foraminal\s+(?:stenosis|narrowing)\b", re.I),
    re.compile(r"\b(?:neural\s+|intervertebral\s+)?foram(?:ina|en)\s+(?:are|is)\s+(?:widely\s+)?patent\b", re.I),
    re.compile(r"\b(?:bilateral\s+)?(?:neural\s+|intervertebral\s+)?foram(?:ina|en)\s+patent\b", re.I),
]

# Hedged / equivocal patterns
FSS_HEDGED_PATTERNS = [
    re.compile(r"\b(?:questionable|equivocal|possible|probable|suspicious\s+for)\s+(?:mild\s+)?(?:narrowing|stenosis)\s+(?:of\s+)?(?:the\s+)?(?:both\s+)?(?:right\s+|left\s+|bilateral\s+)?(?:neural\s+|intervertebral\s+)?foram\w*", re.I),
    re.compile(r"\b(?:neural\s+|intervertebral\s+)?foraminal\s+stenosis\s*\?", re.I),
    re.compile(r"\bnarrowing\s+(?:the\s+)?(?:neural\s+|intervertebral\s+)?foram\w*\s*\?", re.I),
]

# Direct affirmative patterns
FSS_AFFIRMATIVE_PATTERNS = [
    re.compile(r"\bnarrowing\s+(?:of\s+)?(?:the\s+)?(?:both\s+)?(?:right\s+|left\s+|bilateral\s+)?(?:neural\s+|intervertebral\s+)?foram(?:en|ina)\b", re.I),
    re.compile(r"\b(?:neural\s+|intervertebral\s+)?foraminal\s+(?:stenosis|narrowing|encroachment|compromise)\b", re.I),
    re.compile(r"\bstenosis\s+(?:of\s+)?(?:the\s+)?(?:both\s+)?(?:right\s+|left\s+|bilateral\s+)?(?:neural\s+|intervertebral\s+)?foram(?:en|ina)\b", re.I),
    re.compile(r"\bforaminal\s+exit\s+stenosis\b", re.I),
]


def evaluate_foraminal_stenosis_standalone(text: str, case_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Evaluates text for standalone resolution of Foraminal Spinal Stenosis."""
    if not text:
        return None

    # Check hedged patterns first
    for pat in FSS_HEDGED_PATTERNS:
        if pat.search(text):
            return {
                "standalone_state": "UC",
                "fallback_rule_id": "FSS_HEDGED_UC",
                "reason_code": "ASSERT_HEDGED",
            }

    # Check affirmative patterns
    for pat in FSS_AFFIRMATIVE_PATTERNS:
        m = pat.search(text)
        if m:
            # Check if immediately preceded by negation in the same sentence
            start_pos = max(0, m.start() - 40)
            prefix = text[start_pos:m.start()].lower()
            if any(neg in prefix for neg in ["no ", "without ", "not ", "denies ", "ruled out "]):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FSS_EXPLICIT_NEGATION_C",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FSS_CURRENT_AFFIRMATIVE_S",
                "reason_code": "ASSERT_DIRECT_CURRENT",
            }

    # Check explicit negation patterns
    for pat in FSS_NEGATION_PATTERNS:
        if pat.search(text):
            return {
                "standalone_state": "C",
                "fallback_rule_id": "FSS_EXPLICIT_NEGATION_C",
                "reason_code": "ASSERT_TARGET_NEGATED",
            }

    return None
