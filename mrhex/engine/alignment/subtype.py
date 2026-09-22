"""R07 — Subtype / Lineage / Equivalence Gate.

Enforces strict lexical equivalence and ontological directionality.
Distinguishes confirmed subtype exclusions from unresolved lineage ambiguities.

Policy:
  - Confirmed excluded subtype safely blocks S and supports U (SAFE_RULE).
  - Broad category → narrow target: LINEAGE_UNESTABLISHED → ROUTE_TO_LLM.
  - Unvalidated equivalence → ROUTE_TO_LLM.
  - Do NOT create new ontological relationships from general knowledge.
  - Uses word-bounded matching (RETIRE v1 unbounded _configured_hit).
"""
from __future__ import annotations

import re

from mrhex.engine.types import (
    AlignmentStatus,
    ReasonCode,
)


def _word_bounded_pattern(term: str) -> re.Pattern:
    """Compile a word-bounded, case-insensitive pattern for a subtype term."""
    escaped = re.escape(term.strip()).replace(r"\ ", r"[\s-]+")
    return re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)


def check_subtype_alignment(
    clause: str,
    excluded_subtypes: list[str],
    excluded_terms: list[str],
    sentence_context: str = "",
    target_pathology: str = "",
    matched_term: str = "",
) -> tuple[AlignmentStatus, list[ReasonCode]]:
    """Check subtype/lineage alignment for an evidence mention.

    Args:
        clause: The clause text containing the evidence mention.
        excluded_subtypes: Explicitly excluded subtypes from codebook.
        excluded_terms: Additional excluded terms.
        sentence_context: Broader sentence context.
        target_pathology: Target pathology being evaluated.
        matched_term: Specific matched pattern/term ID.

    Returns:
        (AlignmentStatus, list of reason codes)
    """
    reasons: list[ReasonCode] = []
    search_text = f"{clause} {sentence_context}"

    # Clinician Round 2 Policy R2-Q2 hardening for Cerebral atrophy:
    # Postoperative defect, lobectomy, resection, encephalomalacia, or developmental hypoplasia
    # must NOT support Cerebral atrophy S unless explicit 'atrophy' is independently described.
    if target_pathology == "Cerebral atrophy" and matched_term == "COMP_ATROPHY_FOCAL_VOLUME_LOSS":
        if re.search(r'\b(?:postoperative|post-operative|postop|lobectomy|resection|surgical\s+defect|surgical\s+cavity|prior\s+surgery|encephalomalacia|hypoplasia|congenital|developmental)\b', search_text, re.I):
            if not re.search(r'\batrophy\b', search_text, re.I):
                reasons.append(ReasonCode.SUBTYPE_MISMATCH)
                return AlignmentStatus.CONFIRMED_MISMATCH, reasons

    # Check for confirmed excluded subtypes
    for term in excluded_subtypes:
        if not term.strip():
            continue
        if _word_bounded_pattern(term).search(search_text):
            reasons.append(ReasonCode.SUBTYPE_MISMATCH)
            return AlignmentStatus.CONFIRMED_MISMATCH, reasons

    # Check for additional excluded terms
    for term in excluded_terms:
        if not term.strip():
            continue
        if _word_bounded_pattern(term).search(search_text):
            reasons.append(ReasonCode.SUBTYPE_MISMATCH)
            return AlignmentStatus.CONFIRMED_MISMATCH, reasons

    return AlignmentStatus.ALIGNED, reasons


def check_lineage_established(
    matched_term: str,
    positive_terms: list[str],
) -> tuple[bool, list[ReasonCode]]:
    """Check whether the matched term is a validated equivalent in the positive terms list.

    If the matched term is not in the curated positive terms, it may represent
    an unvalidated equivalence that should route to LLM.

    Args:
        matched_term: The term that was matched in the report.
        positive_terms: The curated list of positive vocabulary terms.

    Returns:
        (is_established, list of reason codes)
    """
    # The matched_term should already come from the positive_terms list
    # via the vocabulary/matcher pipeline. This is a safety verification.
    term_lower = matched_term.strip().lower()
    for pt in positive_terms:
        if pt.strip().lower() == term_lower:
            return True, []

    # If we got here, the term was matched but isn't in the curated list
    return False, [ReasonCode.UNVALIDATED_EQUIVALENCE]


def check_lineage_unestablished(
    matched_term: str,
    clause: str,
    insufficient_evidence_terms: list[str],
) -> tuple[bool, list[ReasonCode]]:
    """Check if the matched term or context represents a broad category without specific lineage.
    
    Policy R07:
    Broad categories (e.g. 'mass', 'tumor', 'lesion', 'neoplasm') must not be
    promoted to narrower lineages (e.g. 'glioma') deterministically.
    
    Args:
        matched_term: The term that matched.
        clause: The clause context.
        insufficient_evidence_terms: Broad terms from approved codebook that are
            insufficient alone to establish the target.
            
    Returns:
        (is_unestablished, list of reason codes)
    """
    if not insufficient_evidence_terms:
        return False, []
        
    for term in insufficient_evidence_terms:
        if not term.strip():
            continue
        # If the matched term itself is one of the broad insufficient terms
        if _word_bounded_pattern(term).search(matched_term):
            return True, [ReasonCode.LINEAGE_UNESTABLISHED]
            
    return False, []

