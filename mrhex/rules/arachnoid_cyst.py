"""Pathology-specific standalone fallback rules for Arachnoid Cyst (Batch 12).

Target pathology: 'Arachnoid cyst'

Handles:
- Explicit negation (e.g. 'no arachnoid cyst', 'without arachnoid cyst') -> C
- Hedged / differential findings (e.g. 'arachnoid cyst?', 'araknoid kist?') -> UC
- Direct affirmative arachnoid cyst / arachnoid cystic structure -> S
"""
import re
from typing import Optional, Dict, Any

# Target mentions for missing lexical variants: 'arachnoid cystic structure/lesion'
AC_TARGET = re.compile(
    r"\b(?:"
    r"arachnoid\s+cystic\s+(?:structure|lesion)s?|"
    r"araknoid\s+kistik\s+(?:yap[ıi]|lezyon)(?:lar)?"
    r")\b",
    re.I,
)


# Hedged patterns (no trailing \b right after \?)
AC_HEDGED = re.compile(
    r"(?:"
    r"\barachnoid\s+cysts?\s*\?|"
    r"\baraknoid\s+kist(?:leri)?\s*\?|"
    r"\barachnoid\s+cystic\s+(?:structure|lesion)s?\s*\?|"
    r"\bsuspicious\s+for\s+(?:an\s+)?arachnoid\s+cyst|"
    r"\bdifferential\s+diagnosis\s+includes\s+(?:an\s+)?arachnoid\s+cyst|"
    r"\bay[ıi]r[ıi]c[ıi]\s+tan[ıi].*?araknoid\s+kist|"
    r"\bprimarily\s+evaluated\s+as\s+consistent\s+with\s+an\s+arachnoid\s+cyst\.\s+differential\s+diagnosis"
    r")",
    re.I,
)

# Negation patterns
AC_NEG = re.compile(
    r"\b(?:"
    r"(?:no|without|denies|negative\s+for|ruled\s+out)\s+(?:evidence\s+of\s+)?(?:an\s+)?(?:intracranial\s+)?(?:arachnoid\s+cysts?|arachnoid\s+cystic\s+(?:structure|lesion)s?)|"
    r"(?:araknoid\s+kist|araknoid\s+kistik\s+yap[ıi])\s+(?:lehine\s+)?(?:bulgu\s+)?(?:saptanma(?:d[ıi]|m[ıi][şs])|yoktur)"
    r")\b",
    re.I,
)



def evaluate_arachnoid_cyst_standalone(text: str, case_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Evaluates text for standalone resolution of Arachnoid cyst."""
    if not text:
        return None

    if not AC_TARGET.search(text):
        return None

    if AC_NEG.search(text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "AC_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    if AC_HEDGED.search(text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "AC_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    return {
        "standalone_state": "S",
        "fallback_rule_id": "AC_CURRENT_AFFIRMATIVE_S",
        "reason_code": "ASSERT_DIRECT_CURRENT",
    }

