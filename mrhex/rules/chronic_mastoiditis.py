"""Pathology-specific standalone fallback rules for Chronic Mastoiditis (Batch 12).

Target pathology: 'Chronic mastoiditis'

Handles:
- Explicit negation (e.g. 'no mastoiditis', 'without mastoiditis') -> C
- Prior / historical / sequela findings (e.g. 'prior mastoiditis', 'sequela of prior mastoiditis', 'geçirilmiş mastoidit') -> H
- Hedged findings (e.g. 'suggestive of chronic mastoiditis', 'otomastoiditis?', 'clinical evaluation for mastoiditis') -> UC
- Explicit affirmative chronic mastoiditis -> S
- Isolated effusion / fluid / mucosal thickening without mastoiditis diagnosis returns None (does NOT trigger S)
"""
import re
from typing import Optional, Dict, Any

# Explicit affirmative chronic mastoiditis
CM_AFFIRMATIVE = re.compile(
    r"\b(?:"
    r"chronic\s+mastoiditis|"
    r"chronic\s+otomastoiditis|"
    r"acute-on-chronic\s+mastoiditis|"
    r"kronik\s+mastoidit(?:ler)?|"
    r"kronik\s+otomastoidit(?:ler)?"
    r")\b",
    re.I,
)

# Prior / historical / sequela
CM_PRIOR = re.compile(
    r"\b(?:"
    r"(?:prior|history\s+of|sequela(?:e)?\s+of)\s+(?:prior\s+)?mastoiditis|"
    r"ge[çc]irilmi[şs]\s+mastoidit|"
    r"mastoidit\s+sekeli"
    r")\b",
    re.I,
)

# Hedged patterns (no trailing \b right after \?)
CM_HEDGED = re.compile(
    r"(?:"
    r"\b(?:suggestive\s+of|suspicious\s+for|compatible\s+with|consistent\s+with)\s+chronic\s+mastoiditis|"
    r"\bchronic\s+mastoiditis[^.\n;]{0,30}\?|"
    r"\botomastoiditis\?|"
    r"\bclinical\s+evaluation\s+for\s+mastoiditis|"
    r"\bkronik\s+mastoidit[^.\n;]{0,30}(?:düşündürür|lehine\s+değerlendiril|şüpheli|\?)"
    r")",
    re.I,
)

# Negation patterns
CM_NEG = re.compile(
    r"\b(?:"
    r"(?:no|without|denies|negative\s+for|ruled\s+out)\s+(?:evidence\s+of\s+)?(?:chronic\s+)?mastoiditis|"
    r"mastoidit\s+(?:lehine\s+)?(?:bulgu\s+)?(?:saptanma(?:d[ıi]|m[ıi][şs])|yoktur)"
    r")\b",
    re.I,
)


def evaluate_chronic_mastoiditis_standalone(text: str, case_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Evaluates text for standalone resolution of Chronic mastoiditis."""
    if not text:
        return None

    # 1. Negation
    if CM_NEG.search(text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "CM_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    # 2. Historical / Prior
    if CM_PRIOR.search(text):
        return {
            "standalone_state": "H",
            "fallback_rule_id": "CM_PRIOR_HISTORICAL_H",
            "reason_code": "ASSERT_HISTORICAL_ONLY",
        }

    # 3. Hedged
    if CM_HEDGED.search(text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "CM_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    # 4. Current Affirmative
    if CM_AFFIRMATIVE.search(text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CM_CURRENT_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
        }

    return None
