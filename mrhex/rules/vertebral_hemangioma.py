"""Narrow standalone resolver requiring vertebral osseous hemangioma context."""
from __future__ import annotations
import re
from typing import Any
_PAIR=re.compile(r"\b(?:vertebr\w*(?:\s+(?:body|bodies))?[^.\n]{0,90}hemangiom\w*|hemangiom\w*[^.\n]{0,90}vertebr\w*)\b",re.I)
_NEG=re.compile(r"\b(?:no|without|absent)\s+(?:vertebral\s+)?hemangiom",re.I)
_HIST=re.compile(r"\b(?:history of|status post|previous)\s+(?:vertebral\s+)?hemangiom",re.I)
_HEDGE=re.compile(r"\b(?:possible|possibly|likely|compatible with|\?)\b",re.I)
def evaluate_vertebral_hemangioma_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    if _NEG.search(text): return {"standalone_state":"C","fallback_rule_id":"VERTEBRAL_HEMANGIOMA_NEGATED_C","reason_code":"ASSERT_TARGET_NEGATED"}
    if _HIST.search(text) and not _PAIR.search(text): return {"standalone_state":"H","fallback_rule_id":"VERTEBRAL_HEMANGIOMA_HISTORY_H","reason_code":"HISTORICAL_ONLY"}
    if not _PAIR.search(text): return None
    local=next((s for s in re.split(r"[.\n]+", text) if _PAIR.search(s)), text)
    state="UC" if _HEDGE.search(local) else "S"
    return {"standalone_state":state,"fallback_rule_id":"VERTEBRAL_HEMANGIOMA_OSSEOUS_"+state,"reason_code":"ASSERT_HEDGED" if state=="UC" else "ASSERT_DIRECT_CURRENT"}
