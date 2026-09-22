"""No-match / U / NEI fallback logic.

Policy (Section 16 of task):
  A. adequate report, no target evidence → potentially U / SAFE_RULE
  B. explicitly unavailable or uninterpretable → potentially NEI / SAFE_RULE
  C. adequacy unclear → ROUTE_TO_LLM

Do NOT preserve v1's blanket 'no lexical match → route'.
Do NOT infer report adequacy from report length alone.
"""
from __future__ import annotations

import re

from mrhex.engine.retrieval.sections import section_for_offsets
from mrhex.engine.segmentation.clauses import clause_for_offset
from mrhex.engine.segmentation.sentences import sentence_for_offset
from mrhex.engine.types import (
    EvidenceState,
    ReasonCode,
    RoutingDecision,
    Section,
    SectionSpan,
)

# Patterns indicating explicit severe examination limitation (adequate coverage unavailable)
SEVERE_LIMITATION_PATTERNS = [
    re.compile(r"\b(?:non-diagnostic|technically\s+inadequate|uninterpretable|cannot\s+be\s+(?:adequately\s+)?assessed|incomplete\s+(?:study|exam|examination))\b", re.I),
]

# Patterns indicating partial or ambiguous limitation
PARTIAL_LIMITATION_PATTERNS = [
    re.compile(r"\b(?:limited\s+(?:study|exam|examination|evaluation)|motion\s+artifact|degraded\s+by|suboptimal|partially\s+obscured)\b", re.I),
]

# Patterns indicating affirmative assessment of anatomical structures or normality
ANATOMICAL_ASSESSMENT_PATTERNS = [
    re.compile(r"\b(?:normal|unremarkable|patent|symmetric|within\s+normal\s+limits|preserved|intact)\b", re.I),
    re.compile(r"\b(?:no\s+(?:focal|acute|intracranial|significant|other)\s+(?:abnormality|pathology|mass|hemorrhage|infarct))\b", re.I),
    re.compile(r"\b(?:ventricles?|sulci|parenchyma|brainstem|cerebell(?:um|ar)|hemispheres?|basal\s+ganglia|white\s+matter|cortex|cisterns?)\b", re.I),
]

# Related non-equivalent pattern safety gates
_RELATED_NEGATION = re.compile(
    r"\b(?:no|not|without|negative for|absent|absence of|free of|denies|ruled out|unremarkable|normal|not observed|not seen|not detected|not identified)\b",
    re.I,
)

_RELATED_HISTORICAL = re.compile(
    r"\b(?:history of|hx of|prior|previous|remote|old|previously|status post|s/p|resolved|resolution|remnant|sequela|sequelae)\b",
    re.I,
)

_RELATED_HEDGED = re.compile(
    r"\b(?:possible|possibly|probable|probably|likely|may|might|could|cannot exclude|cannot be excluded|suspicious for|suggestive of|suggests?|suggesting|questionable|favored|favoring|in favor of|thought to be|presumed|differential|versus|vs\.?)\b",
    re.I,
)



def _has_imaging_coverage_evidence(text: str) -> bool:
    """Check if the text provides affirmative evidence of radiological assessment."""
    if not text.strip():
        return False
    # Check for anatomical structure assessment or normal finding survey
    matches = sum(1 for p in ANATOMICAL_ASSESSMENT_PATTERNS if p.search(text))
    return matches >= 1


def classify_no_match(
    report_text: str,
    sections_present: set[Section],
    target_pathology: str,
    source_mode: str = "full_report",
    related_non_equivalent_patterns: list[dict] | None = None,
) -> tuple[EvidenceState | None, RoutingDecision, list[str], list[str]]:
    """Classify a case where no target vocabulary matched.

    Policy Conformance (Tasks 1, 2, 5, 11, P2):
      A. Readable report, no target match → ROUTE_TO_LLM with
         reason TARGET_RETRIEVAL_INCOMPLETE and trigger TRG_TARGET_RETRIEVAL_UNCERTAINTY.
      B. Explicitly unavailable or uninterpretable coverage → NEI / SAFE_RULE.
      C. Partial limitation → ROUTE_TO_LLM with TRG_LIMITED_COVERAGE.
      D. Codebook-backed related non-equivalent finding → U / SAFE_RULE with
         reason RELATED_NON_EQUIVALENT_FINDING.
      E. ZERO character-count or text-length heuristics.

    Args:
        report_text: Full report text.
        sections_present: Set of sections found in the report.
        target_pathology: Target pathology label.
        source_mode: "findings" or "full_report".
        related_non_equivalent_patterns: Optional list of approved non-equivalent pattern dicts.

    Returns:
        tuple of:
          - deterministic_state: EvidenceState or None
          - routing_decision: RoutingDecision
          - reason_codes: list of reason code strings
          - routing_triggers: list of trigger IDs (if routed)
    """
    clean_text = report_text.strip() if report_text else ""

    # Case 1: Empty or whitespace-only report -> NEI via SAFE_RULE
    if not clean_text:
        return (
            EvidenceState.NEI,
            RoutingDecision.SAFE_RULE,
            [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value],
            [],
        )

    # Case 2: Severe explicit technical limitation rendering exam uninterpretable
    if any(p.search(clean_text) for p in SEVERE_LIMITATION_PATTERNS):
        return (
            EvidenceState.NEI,
            RoutingDecision.SAFE_RULE,
            [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value],
            [],
        )

    # Case 3: Partial or ambiguous limitation (e.g. motion artifact) coexisting with text
    if any(p.search(clean_text) for p in PARTIAL_LIMITATION_PATTERNS):
        return (
            None,
            RoutingDecision.ROUTE_TO_LLM,
            [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value],
            ["TRG_LIMITED_COVERAGE"],
        )

    # Case 4: Codebook-backed related non-equivalent finding -> U / SAFE_RULE (Phase 9)
    if related_non_equivalent_patterns and report_text:
        for p_def in related_non_equivalent_patterns:
            pat_str = p_def.get("pattern", "") if isinstance(p_def, dict) else str(p_def)
            if not pat_str:
                continue

            try:
                cpat = re.compile(pat_str, re.I)
            except re.error:
                continue

            for match in cpat.finditer(report_text):
                m_start, m_end = match.start(), match.end()

                # Safety Gate 1: Skip if located in CLINICAL_HISTORY
                sec = section_for_offsets(report_text, m_start, m_end, source_mode=source_mode)
                if sec == Section.CLINICAL_HISTORY:
                    continue

                # Scope to local sentence and clause
                sent_text, s_start, s_end = sentence_for_offset(report_text, m_start)
                clause_text, _, _ = clause_for_offset(sent_text, s_start, m_start)

                # Safety Gate 2: Skip if negated locally
                if _RELATED_NEGATION.search(clause_text):
                    continue

                # Safety Gate 3: Skip if historical
                if _RELATED_HISTORICAL.search(clause_text):
                    continue

                # Safety Gate 4: Skip if hedged
                if _RELATED_HEDGED.search(clause_text):
                    continue

                # Confirmed current imaging finding of an approved non-equivalent finding
                return (
                    EvidenceState.U,
                    RoutingDecision.SAFE_RULE,
                    [ReasonCode.RELATED_NON_EQUIVALENT_FINDING.value],
                    [],
                )


    # Case 5: Readable report with no target match
    # Policy Task 7: For P1/P2, disable general NO_TARGET_LITERAL_MATCH -> U / SAFE_RULE
    # until a validated per-label retrieval completeness contract exists.
    # No target match in a readable report routes to LLM with TARGET_RETRIEVAL_INCOMPLETE
    # and TRG_TARGET_RETRIEVAL_UNCERTAINTY (distinct from LIMITED_EXAM_OR_COVERAGE).
    return (
        None,
        RoutingDecision.ROUTE_TO_LLM,
        [ReasonCode.TARGET_RETRIEVAL_INCOMPLETE.value],
        ["TRG_TARGET_RETRIEVAL_UNCERTAINTY"],
    )

