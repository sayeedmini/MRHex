"""Pathology-specific standalone fallback rules for Schwannoma (Batch 11).

Target pathology: 'Schwannoma'

Handles:
- Explicit negation (e.g. 'no schwannoma', 'no acoustic neuroma') -> C
- Hedged / differential findings (e.g. 'potentially compatible with probable Vestibular Schwannoma',
  'schwannoma?', 'acoustic neuroma?', 'suspicious for schwannoma', 'it may be a 3rd nerve schwannoma') -> UC
- Direct affirmative schwannoma / acoustic neuroma / neurinoma -> S
"""
import re
from typing import Optional, Dict, Any

# Target mention
SCH_TARGET = re.compile(
    r"\b(?:vestibular\s+schwannomas?|acoustic\s+neuromas?|neurinomas?|(?:intradural\s+|trigeminal\s+|cervical\s+|spinal\s+)?schwannomas?)\b",
    re.I,
)

# Hedged patterns
SCH_HEDGED = re.compile(
    r"\b(?:potentially\s+compatible\s+with\s+probable|suspicious\s+for|differential\s+diagnosis)\b"
    r"|\b(?:schwannoma|acoustic\s+neuroma|neurinoma)s?\s*\?"
    r"|\bmay\s+be\s+(?:a\s+)?(?:\w+\s+){0,3}schwannoma\b"
    r"|\bschwannoma\s+may\s+also\s+be\s+considered\b",
    re.I,
)

# Negation patterns
SCH_NEG = re.compile(
    r"\b(?:no|without|denies|negative\s+for|ruled\s+out)\s+(?:evidence\s+of\s+)?(?:significant\s+)?(?:vestibular\s+)?(?:schwannoma|acoustic\s+neuroma)\b",
    re.I,
)


def evaluate_schwannoma_standalone(text: str, case_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Evaluates text for standalone resolution of Schwannoma."""
    if not text:
        return None

    # Focus on Findings and Impression sections if present
    sections = re.split(r"\n(?=[A-Z][A-Za-z\s]+:)", text)
    fi_text = ""
    for s in sections:
        header = s.split(":")[0].strip().upper()
        if header in ("FINDINGS", "IMPRESSION"):
            fi_text += s + "\n"
    eval_text = fi_text if fi_text else text

    if SCH_NEG.search(eval_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "SCH_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    if SCH_HEDGED.search(eval_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "SCH_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    if SCH_TARGET.search(eval_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "SCH_CURRENT_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
        }

    return None
