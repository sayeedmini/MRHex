"""Deterministic Standalone Fallback Rules for Pituitary Adenoma.

Implements accepted standalone rules:
  - PA-ST-1: Postoperative / surgically resected / treated adenoma without residual lesion -> H
  - PA-ST-2: Hedged, equivocal, differential, or Impression question-mark override -> UC
  - PA-ST-3: Affirmed current sellar microadenoma, macroadenoma, or active residual/recurrent adenoma -> S
  - PA-ST-4: Explicit negation of sellar adenoma -> C

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# Anatomical Anchors and Non-Pituitary Exclusions
# ------------------------------------------------------------------------------
PITUITARY_SELLAR_ANCHOR = re.compile(
    r"\b(?:pituitary|hypophysis|adenohypophysis|neurohypophysis|sella|sellar|intrasellar|suprasellar|pituitary\s+fossa|pituitary\s+stalk|infundibulum)\b",
    re.I,
)

NON_PITUITARY_ADENOMA_EXCLUSION = re.compile(
    r"\b(?:adrenal|parathyroid|pleomorphic|hepatic|thyroid|salivary|colon|tubular|villous|sebaceous)\s+adenoma\b",
    re.I,
)

# ------------------------------------------------------------------------------
# PA-ST-1: Postoperative / Resected / Treated Without Active Residual -> H
# ------------------------------------------------------------------------------
PA_ST1_POSTOP_SURGERY = re.compile(
    r"(?:"
    r"adenoma\s+excision|"
    r"pituitary\s+adenoma\s+excision|"
    r"transsphenoidal\s+(?:pituitary\s+)?adenoma\s+excision|"
    r"transsphenoidal\s+hypophysectomy\s+for\s+pituitary\s+adenoma|"
    r"adenoma\s+surgery|"
    r"status\s+post\s+(?:pituitary\s+)?adenoma\s+resection|"
    r"previously\s+operated\s+(?:pituitary\s+)?adenoma|"
    r"history\s+of\s+(?:pituitary\s+)?adenoma\s+surgery|"
    r"(?:under\s+)?follow-up\s+and\s+treatment\s+(?:due\s+to|for)\s+(?:pituitary\s+)?(?:macro|micro)?\s*adenoma"
    r")",
    re.I | re.DOTALL,
)

PA_ST1_NO_RESIDUAL = re.compile(
    r"(?:"
    r"no\s+(?:definite\s+|clearly\s+identifiable\s+|obvious\s+|residual\s+or\s+recurrent\s+|recurrent\s+or\s+residual\s+)?(?:residual|recurrent|recurrence)(?:\s+(?:pituitary\s+)?(?:macro|micro)?\s*adenoma|\s+tumor|\s+mass|\s+lesion)?|"
    r"no\s+lesion\s+with\s+a\s+defined\s+contour|"
    r"empty\s+sella|"
    r"no\s+enhancing\s+mass"
    r")",
    re.I,
)

PA_ST1_ACTIVE_RESIDUAL = re.compile(
    r"(?:"
    r"residual[\-\s]recurrent\s+(?:macro|micro)?\s*adenoma|"
    r"residual\s+(?:viable\s+)?(?:macro|micro)?\s*adenoma|"
    r"recurrent\s+(?:macro|micro)?\s*adenoma|"
    r"residual[\-\s]recurrent\s+adenoma|"
    r"residual\s+adenoma|"
    r"recurrent\s+adenoma"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# PA-ST-2: Hedged / Differential / Impression Question Override -> UC
# ------------------------------------------------------------------------------
PA_ST2_IMPRESSION_QUESTION = re.compile(
    r"(?:"
    r"\((?:cystic\s+)?(?:micro|macro)?\s*adenoma\s*\?\)|"
    r"\b(?:micro|macro)?\s*adenoma\w*\s*\?|"
    r"\b(?:micro|macro)?\s*adenoma\w*\s*\.{2,}\?|"
    r"\b(?:micro|macro)?\s*adenoma\b.*?\?"
    r")",
    re.I,
)

PA_ST2_HEDGED = re.compile(
    r"(?:"
    r"\((?:cystic\s+)?(?:micro|macro)?\s*adenoma\s*\?\)|"
    r"\b(?:micro|macro)?\s*adenoma\s*\?|"
    r"\b(?:micro|macro)?\s*adenoma\s*\.{2,}\?|"
    r"suspicious\s+(?:for\s+|and\s+hypointense.*?potentially\s+a\s+)?(?:cystic\s+)?(?:micro|macro)?\s*adenoma|"
    r"potentially\s+(?:compatible\s+with\s+a\s+)?(?:cystic\s+)?(?:micro|macro)?\s*adenoma|"
    r"possible\s+(?:pituitary\s+)?(?:micro|macro)?\s*adenoma|"
    r"cannot\s+(?:exclude|rule\s+out)\s+(?:pituitary\s+)?(?:micro|macro)?\s*adenoma|"
    r"suggestive\s+of\s+(?:a\s+)?(?:pituitary\s+)?(?:micro|macro)?\s*adenoma|"
    r"thought\s+to\s+be\s+(?:a\s+)?(?:pituitary\s+)?(?:micro|macro)?\s*adenoma|"
    r"questionable\s+(?:pituitary\s+)?(?:micro|macro)?\s*adenoma|"
    r"pars\s+intermedia\s+cyst\s+(?:or|vs\.?)\s+(?:cystic\s+)?micro\s*adenoma|"
    r"cystic\s+micro\s*adenoma\s+(?:or|vs\.?)\s+pars\s+intermedia\s+cyst|"
    r"(?:differentiation\s+between\s+)?cystic\s+micro\s*adenoma\s+and\s+pars\s+intermedia\s+cyst|"
    r"macroadenoma\s*\?\s*meningioma\s*\?|"
    r"meningioma\s*\?\s*macroadenoma\s*\?|"
    r"(?:Rathke\s+cleft\s+cyst|pars\s+intermedia\s+cyst)\s+(?:or|vs\.?)\s+(?:pituitary\s+)?(?:micro|macro)?\s*adenoma"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# PA-ST-3: Affirmed Current Sellar Microadenoma / Macroadenoma -> S
# ------------------------------------------------------------------------------
PA_ST3_AFFIRMED = re.compile(
    r"(?:"
    r"\b(?:residual[\-\s]recurrent\s+|recurrent\s+|residual\s+)?(?:micro|macro)\s*adenoma\b(?!\s*\?)|"
    r"\bpituitary\s+(?:micro|macro)?\s*adenoma\b(?!\s*\?)|"
    r"\badenoma\s+in\s+the\s+(?:left|right|central)?\s*(?:portion|side|region|area|lobe)?\s*of\s+the\s+(?:adeno)?hypophysis(?!\s*\?)|"
    r"\badenoma\s+of\s+(?:the\s+)?(?:pituitary(?:\s+gland)?|hypophysis)(?!\s*\?)|"
    r"\bPitNET\s*\((?:macroadenoma|microadenoma)\)"
    r")",
    re.I,
)

PA_BARE_ADENOMA = re.compile(r"\badenoma(?:s)?\b(?!\s*\?)", re.I)

# ------------------------------------------------------------------------------
# PA-ST-4: Explicit Negation of Pituitary Adenoma -> C
# ------------------------------------------------------------------------------
PA_NEGATION = re.compile(
    r"\b(?:no\s+(?:evidence\s+of\s+)?|without\s+(?:evidence\s+of\s+)?|negative\s+for\s+|ruled\s+out\s+)"
    r"(?:pituitary\s+)?(?:micro|macro)?\s*adenoma\b",
    re.I,
)


def evaluate_pituitary_adenoma_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Pituitary adenoma."""
    clean_text = text.replace("\r", " ")

    # Priority 1: Resected / Postoperative / Treated without active residual -> H
    if not NON_PITUITARY_ADENOMA_EXCLUSION.search(clean_text):
        m_surg = PA_ST1_POSTOP_SURGERY.search(clean_text)
        if m_surg:
            has_active_residual = bool(PA_ST1_ACTIVE_RESIDUAL.search(clean_text))
            has_no_residual = bool(PA_ST1_NO_RESIDUAL.search(clean_text))
            if has_no_residual and not has_active_residual:
                return {
                    "standalone_state": "H",
                    "fallback_rule_id": "FALLBACK_PA_ST1_POSTOP_H",
                    "reason_code": "HISTORICAL_ONLY",
                    "reason_codes": ["HISTORICAL_ONLY", "POSTOP_RESECTION_NO_RESIDUAL"],
                    "evidence_spans": [{
                        "matched_term": m_surg.group(0)[:80],
                        "polarity": "AFFIRMED",
                        "certainty": "DEFINITE",
                        "clause_text": m_surg.group(0)[:80],
                    }],
                }

    # Priority 2: Impression-level question mark / hedge override -> UC
    in_impression = False
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if re.search(r'\b(?:impression|sonuç)\b', line_clean, re.I):
            in_impression = True
        if in_impression:
            if not NON_PITUITARY_ADENOMA_EXCLUSION.search(line_clean):
                m_imp = PA_ST2_IMPRESSION_QUESTION.search(line_clean)
                if m_imp:
                    return {
                        "standalone_state": "UC",
                        "fallback_rule_id": "FALLBACK_PA_ST2_IMPRESSION_QUESTION_UC",
                        "reason_code": "ASSERT_HEDGED",
                        "reason_codes": ["ASSERT_HEDGED", "IMPRESSION_QUESTION_MARK_OVERRIDE"],
                        "evidence_spans": [{
                            "matched_term": m_imp.group(0),
                            "polarity": "AFFIRMED",
                            "certainty": "HEDGED",
                            "clause_text": line_clean[:120],
                        }],
                    }

    # Priority 2b: Report-level hedged / differential adenoma -> UC
    if not NON_PITUITARY_ADENOMA_EXCLUSION.search(clean_text):
        m_hedge = PA_ST2_HEDGED.search(clean_text)
        if m_hedge:
            # Verify anatomical anchor if bare adenoma
            term = m_hedge.group(0)
            if "adenoma" in term.lower() and not any(k in term.lower() for k in ["micro", "macro", "pituitary"]):
                if not PITUITARY_SELLAR_ANCHOR.search(clean_text):
                    m_hedge = None
            if m_hedge:
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_PA_ST2_HEDGED_UC",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "HEDGED_OR_DIFFERENTIAL_ADENOMA"],
                    "evidence_spans": [{
                        "matched_term": m_hedge.group(0),
                        "polarity": "AFFIRMED",
                        "certainty": "HEDGED",
                        "clause_text": m_hedge.group(0),
                    }],
                }

    # Priority 3: Affirmed Current Sellar Microadenoma / Macroadenoma -> S
    if not NON_PITUITARY_ADENOMA_EXCLUSION.search(clean_text):
        m_aff = PA_ST3_AFFIRMED.search(clean_text)
        if m_aff:
            matched_span = m_aff.group(0)
            start_idx = m_aff.start()
            prefix = clean_text[max(0, start_idx - 60):start_idx]
            if not re.search(r"\b(?:no|without|absence\s+of|ruled\s+out|negative\s+for)\s*$", prefix, re.I):
                return {
                    "standalone_state": "S",
                    "fallback_rule_id": "FALLBACK_PA_ST3_AFFIRMED_S",
                    "reason_code": "ASSERT_DIRECT_CURRENT",
                    "reason_codes": ["ASSERT_DIRECT_CURRENT", "AFFIRMED_SELLAR_ADENOMA"],
                    "evidence_spans": [{
                        "matched_term": matched_span,
                        "polarity": "AFFIRMED",
                        "certainty": "DEFINITE",
                        "clause_text": matched_span,
                    }],
                }

        # Check bare adenoma with sellar anchor
        if PITUITARY_SELLAR_ANCHOR.search(clean_text):
            m_bare = PA_BARE_ADENOMA.search(clean_text)
            if m_bare:
                start_idx = m_bare.start()
                prefix = clean_text[max(0, start_idx - 60):start_idx]
                if not re.search(r"\b(?:no|without|absence\s+of|ruled\s+out|negative\s+for)\s*$", prefix, re.I):
                    for sent in re.split(r'[.\n]', clean_text):
                        if m_bare.group(0) in sent and PITUITARY_SELLAR_ANCHOR.search(sent):
                            return {
                                "standalone_state": "S",
                                "fallback_rule_id": "FALLBACK_PA_ST3_BARE_ADENOMA_ANCHORED_S",
                                "reason_code": "ASSERT_DIRECT_CURRENT",
                                "reason_codes": ["ASSERT_DIRECT_CURRENT", "AFFIRMED_BARE_ADENOMA_SELLAR"],
                                "evidence_spans": [{
                                    "matched_term": m_bare.group(0),
                                    "polarity": "AFFIRMED",
                                    "certainty": "DEFINITE",
                                    "clause_text": sent.strip()[:100],
                                }],
                            }

    # Priority 4: Explicit Negation of Pituitary Adenoma -> C
    if not NON_PITUITARY_ADENOMA_EXCLUSION.search(clean_text):
        m_neg = PA_NEGATION.search(clean_text)
        if m_neg:
            return {
                "standalone_state": "C",
                "fallback_rule_id": "FALLBACK_PA_ST4_NEGATED_C",
                "reason_code": "ASSERT_TARGET_NEGATED",
                "reason_codes": ["ASSERT_TARGET_NEGATED", "EXPLICIT_NEGATION_ADENOMA"],
                "evidence_spans": [{
                    "matched_term": m_neg.group(0),
                    "polarity": "NEGATED",
                    "certainty": "DEFINITE",
                    "clause_text": m_neg.group(0),
                }],
            }

    return None
