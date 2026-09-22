"""Deterministic Standalone Resolver for Cavernous hemangioma (Batch 10)."""
from __future__ import annotations

import re
from typing import Any

# Confounders to strictly exclude
_VERTEBRAL_HEMANGIOMA = re.compile(
    r"\b(?:vertebr\w*(?:\s+(?:body|bodies))?[^.\n]{0,90}hemangiom\w*|hemangiom\w*[^.\n]{0,90}vertebr\w*|odontoid\s+vertebra)\b",
    re.I,
)
_VISCERAL_HEMANGIOMA = re.compile(
    r"\b(?:hepatic|liver|soft\s+tissue|skin|scalp|sinonasal|orbital|splenic)\s+(?:cavernous\s+)?hemangioma\b",
    re.I,
)

# Negation
_NEG = re.compile(
    r"\b(?:no|without|absent|negative\s+for|free\s+of)\s+(?:evidence\s+of\s+)?(?:(?:acute|prior|intracranial|cerebral|residual|recurrent)\s+)?(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))s?\b"
    r"|\b(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))s?\s+(?:is|are)?\s*not\s+(?:seen|observed|detected|identified)\b",
    re.I,
)

# Historical / Post-operative
_HIST_OR_POSTOP = re.compile(
    r"\b(?:resection\s+of(?:\s+the)?|operated|status\s+post|s/p|prior\s+surgery\s+for|history\s+of|hx\s+of)\s+[^.\n]{0,50}(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))"
    r"|\boperated\s+(?:[\w-]+\s+){0,3}(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\b"
    r"|\b(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\s+(?:was\s+)?resected\b",
    re.I,
)

# Target mention
_TARGET = re.compile(
    r"\b(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))s?\b",
    re.I,
)

# Hedging (differential, suggestive, question mark, or alternative diagnosis)
_HEDGE = re.compile(
    r"\b(?:suggestive\s+of|suspicious\s+(?:for|of)|possible|possibly|probable|probably|differential|uncertain|cannot\s+(?:rule\s+out|exclude))\s+(?:an?\s+)?(?:[\w-]+\s+)?(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\b"
    r"|\b(?:calcification|microhemorrhage|capillary\s+telangiectasia)\s+or\s+(?:an?\s+)?(?:[\w-]+\s+)?(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\b"
    r"|\b(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))s?\s*(?:or|\?)"
    r"|\b(?:suggests?|considered\s+as\s+a\s+probable)\s+(?:an?\s+)?(?:[\w-]+\s+)?(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\b",
    re.I,
)


def evaluate_cavernous_hemangioma_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Cavernous hemangioma."""
    # Safety: If mention is purely vertebral or visceral hemangioma, exclude
    if _VERTEBRAL_HEMANGIOMA.search(text):
        non_vert = [s for s in re.split(r"[.\n]+", text) if _TARGET.search(s) and not _VERTEBRAL_HEMANGIOMA.search(s)]
        if not non_vert:
            return None
    if _VISCERAL_HEMANGIOMA.search(text):
        non_visc = [s for s in re.split(r"[.\n]+", text) if _TARGET.search(s) and not _VISCERAL_HEMANGIOMA.search(s)]
        if not non_visc:
            return None

    # 1. Negation
    if _NEG.search(text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "CAV_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    # 2. Check for target mention
    if not _TARGET.search(text):
        return None

    # Safety: If the ONLY hemangioma mention is in a vertebral or visceral context
    # and no intracranial/cerebral cavernoma pattern exists
    if _VERTEBRAL_HEMANGIOMA.search(text) and not re.search(r"\b(?:[ck]avernoma|cavernous\s+(?:hemangioma|angioma|malformation))\b", text, re.I):
        return None

    # 3. Post-operative / Historical
    if _HIST_OR_POSTOP.search(text):
        # Check if there is a separate distinct active current lesion outside post-op/resection context
        active_sentences = [
            s for s in re.split(r"[.\n]+", text)
            if _TARGET.search(s) and not _HIST_OR_POSTOP.search(s) and not re.search(r"\b(?:craniotomy|resection|operated|post-?op)\b", s, re.I)
        ]
        if not active_sentences:
            return {
                "standalone_state": "H",
                "fallback_rule_id": "CAV_POSTOP_HISTORICAL_H",
                "reason_code": "HISTORICAL_ONLY",
            }

    # Find the local sentence for hedging analysis
    local_sentence = next(
        (s for s in re.split(r"[.\n]+", text) if _TARGET.search(s)),
        text,
    )

    # 4. Hedging
    if _HEDGE.search(local_sentence):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "CAV_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    # 5. Affirmative
    return {
        "standalone_state": "S",
        "fallback_rule_id": "CAV_CURRENT_AFFIRMATIVE_S",
        "reason_code": "ASSERT_DIRECT_CURRENT",
    }
