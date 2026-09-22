"""Narrow standalone resolver for current, non-mass-effect Chiari wording."""
from __future__ import annotations
import re
from typing import Any

_MASS = re.compile(r"\b(?:mass(?:-like)?|tumou?r|neoplasm|metasta|pilocytic|compress(?:es|ing|ion))\b", re.I)
_HEDGE = re.compile(r"\b(?:\?|possible|possibly|suggestive|suspicious|cannot exclude)\b", re.I)
_NEG = re.compile(r"\b(?:no|without|absent)\s+(?:evidence of\s+)?(?:chiari|tonsillar (?:ectopia|herniation))", re.I)
_HIST = re.compile(r"\b(?:history of|status post|previously)\s+chiari", re.I)
_CURRENT = re.compile(r"\b(?:chiari(?:\s+(?:type\s*)?(?:i|1))?|tonsillar\s+herniation|tonsils?\s+(?:extend|herniat|fill|descend))\b", re.I)
_ANCHOR = re.compile(r"\b(?:foramen magnum|mcrae|basion.?opisthion|craniocervical junction)\b", re.I)

def evaluate_chiari_malformation_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    if _NEG.search(text): return {"standalone_state":"C","fallback_rule_id":"CHIARI_NEGATED_C","reason_code":"ASSERT_TARGET_NEGATED"}
    if _HIST.search(text) and not _CURRENT.search(text): return {"standalone_state":"H","fallback_rule_id":"CHIARI_HISTORY_H","reason_code":"HISTORICAL_ONLY"}
    if _MASS.search(text) or not _CURRENT.search(text): return None
    if not (_ANCHOR.search(text) or re.search(r"\bchiari\b", text, re.I)): return None
    local = next((s for s in re.split(r"[.\n]+", text) if _CURRENT.search(s)), text)
    state = "UC" if _HEDGE.search(local) else "S"
    return {"standalone_state":state,"fallback_rule_id":"CHIARI_CURRENT_ANCHORED_"+state,"reason_code":"ASSERT_HEDGED" if state=="UC" else "ASSERT_DIRECT_CURRENT"}
