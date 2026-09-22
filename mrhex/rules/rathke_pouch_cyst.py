"""Pathology-specific standalone fallback rules for Rathke's pouch cyst (Batch 11).

Target pathology: "Rathke's pouch cyst"

Handles:
- Explicit negation (e.g. 'no Rathke cleft cyst', 'no pars intermedia cyst') -> C
- Hedged / equivocal / differential findings (e.g. 'Rathke cleft cyst?', 'pars intermedia cyst ?',
  'Rathke cleft cyst or microadenoma') -> UC
- Direct affirmative Rathke cleft cyst / pars intermedia cyst -> S
"""
import re
from typing import Optional, Dict, Any

# Target mention
RPC_TARGET = re.compile(
    r"\b(?:pars\s+intermedia\s+cysts?|rathke(?:'s)?\s+(?:cleft|pouch)?\s*cysts?|rathke\s+cysts?)\b",
    re.I,
)

# Hedged / equivocal patterns
RPC_HEDGED = re.compile(
    r"\b(?:pars\s+intermedia\s+cysts?|rathke(?:'s)?\s+(?:cleft|pouch)?\s*cysts?)\s*\?"
    r"|\b(?:rathke(?:'s)?\s+(?:cleft|pouch)?\s*cyst|pars\s+intermedia\s+cyst)\s+(?:or|vs)\b",
    re.I,
)

# Negation patterns
RPC_NEG = re.compile(
    r"\b(?:no|without|denies|negative\s+for|ruled\s+out)\s+(?:evidence\s+of\s+)?(?:rathke(?:'s)?\s+(?:cleft|pouch)?\s*cyst|pars\s+intermedia\s+cyst)\b",
    re.I,
)


def evaluate_rathke_pouch_cyst_standalone(text: str, case_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Evaluates text for standalone resolution of Rathke's pouch cyst."""
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

    if RPC_NEG.search(eval_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "RPC_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    if RPC_HEDGED.search(eval_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "RPC_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    if RPC_TARGET.search(eval_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "RPC_CURRENT_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
        }

    return None
