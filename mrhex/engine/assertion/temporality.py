"""Target-local temporality assertion module for deterministic v2."""
from __future__ import annotations

import re
from typing import Optional

from mrhex.engine.types import TemporalityClass, ReasonCode, Section

HISTORY_CUES = re.compile(
    r'\b(history of|previously resolved|prior diagnosis of|status post treatment for|status post|s/p|remote history of|previous history of|known history of|operated|resected|(?:previously|prior)\s+treated)\b',
    re.I,
)
CHRONIC_CUES = re.compile(
    r'\b(chronic|stable|unchanged|persistent|long-standing|longstanding)\b',
    re.I,
)
OLD_CUES = re.compile(r'\b(old|prior|previous)\b', re.I)
RESIDUAL_CUES = re.compile(r'\b(residual|sequela|sequelae|remnant|remaining)\b', re.I)
REGRESSING_CUES = re.compile(r'\b(decreased|decreasing|improving|interval decrease|reduced|smaller)\b', re.I)
RESOLVED_PRE_CUES = re.compile(r'\b(resolved|previously resolved|disappeared)\b', re.I)
RESOLVED_POST_CUES = re.compile(
    r'^\s*(?:,\s*)?(?:is|are|was|were|has\s+been|have\s+been|appears?|remains?|noted\s+to\s+be)?\s*(?:now|completely|fully|interval)?\s*(resolved|resolution|no longer seen|disappeared)\b',
    re.I,
)
POST_SURGICAL_PROCEDURE_CUES = re.compile(
    r'^\s*(?:,\s*)?(?:excision|resection|removal|surgery|operation)\b',
    re.I,
)
POST_RESIDUAL_CUES = re.compile(
    r'^\s*(?:,\s*)?(?:sequela(?:e)?|residual|remnant)\b',
    re.I,
)
CURRENT_CUES = re.compile(r'\b(current|active|recurrent|new|acute|subacute)\b', re.I)
CLINICAL_INDICATION_CUES = re.compile(
    r'\b(rule out|r/o|evaluate for|assess for|concern for|question of|indication\s*:|symptoms?\s*:|clinical(?:ly)?\s+suspected|clinical\s+suspicion)\b',
    re.I,
)

# Major phrase delimiters that separate distinct entities or clauses
DELIMITER_RE = re.compile(
    r'(?:,\s*with\b|\bwith\b|\bwithout\b|,\s*and\b|\band\b|,\s*but\b|\bbut\b|\bexcept\b|\bhowever\b|\balthough\b|\bwhereas\b|\bwhile\b|\bdue\s+to\b|\bsecondary\s+to\b|;|,)',
    re.I,
)


def analyze_temporality(
    clause: str,
    section: Section,
    target_start: int,
    target_end: int,
    target_pathology: str = "",
    label_overrides: dict | None = None,
    global_overrides: dict | None = None,
) -> tuple[TemporalityClass, list[ReasonCode]]:
    """Analyze temporality and history with target-local scoping.
    
    R05 Policy Conformance:
    - Target-local syntactic attachment:
      A temporal cue may affect the target only when there is a defensible
      syntactic/local relationship between the cue and that specific target mention.
    - Cues belonging to other entities (e.g. 'Resolved middle-ear effusion with persistent mastoiditis')
      do not bleed into the target mention.
    - Clear established history ('history of X', 'prior diagnosis of X'):
      Unconflicted with no current assertion -> HISTORICAL_ONLY (may support H via SAFE_RULE).
    - Resolved disease ('Resolved mastoiditis', 'Previous mastoiditis is now resolved'):
      Maps to RESOLVED with HISTORICAL_ONLY reason code (supports H via SAFE_RULE).
    - Clinical indication / question ('rule out X'):
      CLINICAL_INDICATION with CLINICAL_ONLY_PROVENANCE (routes to LLM).
    - Label-specific temporality overrides:
      * Lacunar infarct: chronic/old -> HISTORICAL_ONLY; acute/age-unspecified -> CURRENT.
      * Watershed infarct: chronic/old -> HISTORICAL_ONLY; acute/age-unspecified -> CURRENT.
      * Cerebral hemorrhage: persisting/chronic hematoma -> CHRONIC_CURRENT (S); resolved residual -> RESOLVED (H).
      * Subdural intracranial hemorrhage: chronic -> CHRONIC_CURRENT (S); resolved -> RESOLVED (H).
    - If cue attachment is genuinely ambiguous: AMBIGUOUS with MALFORMED_OR_COMPLEX_SCOPE.
    
    Args:
        clause: The text of the clause containing the target.
        section: The section provenance of the clause.
        target_start: Start index of the target term in the clause.
        target_end: End index of the target term in the clause.
        target_pathology: The target pathology canonical name.
        label_overrides: Dictionary of label-specific policy overrides.
        global_overrides: Dictionary of global policy overrides.
        
    Returns:
        tuple[TemporalityClass, list[ReasonCode]]: Temporality class and reason codes.
    """
    label_overrides = label_overrides or {}
    global_overrides = global_overrides or {}

    prefix = clause[:target_start]
    suffix = clause[target_end:]

    # 1. If in CLINICAL_HISTORY section or clause explicitly introduced as clinical indication/information
    if section == Section.CLINICAL_HISTORY or re.search(r'\bclinical\s+(?:information|history|indication)\b', prefix, re.I):
        if HISTORY_CUES.search(prefix) or OLD_CUES.search(prefix):
            return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
        return TemporalityClass.CLINICAL_INDICATION, [ReasonCode.CLINICAL_ONLY_PROVENANCE]

    # 2. Check post-target predicative resolution ('Previous mastoiditis is now resolved')
    post_resolved = bool(RESOLVED_POST_CUES.search(suffix))
    post_surgical = bool(POST_SURGICAL_PROCEDURE_CUES.search(suffix))
    post_residual = bool(POST_RESIDUAL_CUES.search(suffix))

    # 3. Delimiter analysis in prefix to establish local governing segment
    delims = list(DELIMITER_RE.finditer(prefix))
    if delims:
        last_delim = delims[-1]
        delim_text = last_delim.group().lower().strip(", ")
        local_prefix = prefix[last_delim.end():]
        prior_prefix = prefix[:last_delim.start()]
    else:
        delim_text = ""
        local_prefix = prefix
        prior_prefix = ""

    # Check cues in local prefix
    has_local_clinical = bool(CLINICAL_INDICATION_CUES.search(local_prefix))
    has_local_history = bool(HISTORY_CUES.search(local_prefix))
    has_local_resolved = bool(RESOLVED_PRE_CUES.search(local_prefix))
    has_local_chronic = bool(CHRONIC_CUES.search(local_prefix))
    has_local_old = bool(OLD_CUES.search(local_prefix))
    has_local_current = bool(CURRENT_CUES.search(local_prefix))
    has_local_residual = bool(RESIDUAL_CUES.search(local_prefix)) or post_residual
    has_local_regressing = bool(REGRESSING_CUES.search(local_prefix))

    # If no local cue, evaluate whether prior prefix cue distributes across delimiter
    if not (has_local_clinical or has_local_history or has_local_resolved or
            has_local_chronic or has_local_old or has_local_current or
            has_local_residual or has_local_regressing):
        if prior_prefix:
            if delim_text in ("and", "or"):
                # Coordinating conjunction distributes governing cue across list items
                # But do NOT distribute if cue in prior clause modifies a surgical procedure/intervention or injury
                is_prior_procedure_or_injury = bool(re.search(
                    r'\b(?:prior|previous|history\s+of|s/p|status\s+post)\s+(?:surgery|operation|resection|procedure|intervention|craniotomy|trauma|injury|insult)\b',
                    prior_prefix,
                    re.I,
                ))
                if CLINICAL_INDICATION_CUES.search(prior_prefix):
                    has_local_clinical = True
                elif HISTORY_CUES.search(prior_prefix) and not is_prior_procedure_or_injury:
                    has_local_history = True
                elif RESOLVED_PRE_CUES.search(prior_prefix):
                    has_local_resolved = True
                elif OLD_CUES.search(prior_prefix) and not is_prior_procedure_or_injury:
                    has_local_old = True
                elif CHRONIC_CUES.search(prior_prefix):
                    has_local_chronic = True
            elif delim_text in ("with", "without", "except", "but", "however", "although", "whereas", "while", "due to", "secondary to"):
                # Prepositional adjunct / contrast: cue in prior clause does NOT attach cleanly to target
                # If prior had a temporal cue, attachment is ambiguous
                if (HISTORY_CUES.search(prior_prefix) or RESOLVED_PRE_CUES.search(prior_prefix) or
                        CLINICAL_INDICATION_CUES.search(prior_prefix)):
                    # Ambiguous cue attachment routes to LLM
                    return TemporalityClass.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]

    # Clinical indication check
    if has_local_clinical:
        return TemporalityClass.CLINICAL_INDICATION, [ReasonCode.CLINICAL_ONLY_PROVENANCE]

    # Resolved disease cues (pre-target 'Resolved X' or post-target 'X is now resolved')
    if has_local_resolved or post_resolved:
        resolved_state = global_overrides.get("resolved_without_current", {}).get("state", "H")
        if resolved_state == "H":
            return TemporalityClass.RESOLVED, [ReasonCode.HISTORICAL_ONLY]
        return TemporalityClass.RESOLVED, [ReasonCode.HISTORICAL_ONLY]

    # Post-target surgical procedure (e.g. 'meningioma excision', 'glioma resection')
    if post_surgical and not (has_local_residual or has_local_current):
        return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]

    # Established history cues
    if has_local_history:
        return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]

    # Label-specific temporality overrides
    if target_pathology == "Watershed infarct":
        # Ensemble-aligned policy:
        # History-only mentions, prior/previous infarcts, or residual sequelae = H.
        # Currently visualized chronic/old watershed infarcts = S (when chronic_present_state == 'S').
        # Acute/subacute or age-unspecified = S.
        chronic_state = label_overrides.get("chronic_present_state", "H")
        if chronic_state == "S":
            if has_local_history:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if re.search(r'\b(?:prior|previous|past)\b', local_prefix, re.I):
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_chronic or has_local_old:
                return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            if has_local_residual or post_residual:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_current:
                return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
        else:
            if has_local_chronic or has_local_old or has_local_residual or post_residual:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_current:
                return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    if target_pathology == "Lacunar infarct":
        # Ensemble-aligned policy:
        # History-only mentions, prior/previous infarcts, or residual sequelae = H.
        # Currently visualized chronic/old lacunar infarcts = S (when chronic_present_state == 'S').
        # Acute/subacute or age-unspecified = S.
        chronic_state = label_overrides.get("chronic_present_state", "H")
        if chronic_state == "S":
            if has_local_history:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if re.search(r'\b(?:prior|previous|past)\b', local_prefix, re.I):
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_chronic or has_local_old:
                return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            if has_local_residual or post_residual:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_current:
                return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
        else:
            if has_local_chronic or has_local_old or has_local_residual or post_residual:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            if has_local_current:
                return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    if target_pathology == "Encephalomalacia":
        # Codebook: Chronic encephalomalacia currently present = S even when the precipitating
        # injury is historical. Include ischemic, traumatic and postoperative encephalomalacia explicitly named.
        # A precipitating historical event, prior surgery, or postoperative context must NOT convert
        # currently present encephalomalacia morphology into HISTORICAL_ONLY.
        is_pure_history = (
            section == Section.CLINICAL_HISTORY
            or (has_local_history and not (has_local_current or re.search(
                r'\b(?:observed|seen|detected|noted|present|t2|flair|hyperintens|gliosis|post-?operative|secondary\s+to|due\s+to|defect|cavity|area|lesion|change)\b',
                clause,
                re.I,
            )))
        )
        if is_pure_history:
            return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
        return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    if target_pathology == "Subdural intracranial hemorrhage":
        # Codebook: Chronic subdural hematoma still present = S. Resolved = H.
        if has_local_chronic:
            return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
        return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    if target_pathology == "Cerebral hemorrhage":
        # Codebook: Persisting/chronic hematoma present = S. Resolved = H.
        if has_local_chronic:
            return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
        return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    if target_pathology == "Intracranial aneurysm":
        # Clinician Policy Round 2 (R2-Q1):
        # When report clearly documents previously treated/coiled/embolized aneurysm
        # without definite current residual/recurrent aneurysm filling -> H (Historical).
        # Material confirms treatment, not residual disease.
        # Definite residual/recurrent filling -> CURRENT (S).
        has_treatment = bool(re.search(
            r'\b(?:coiled|coil\s+mass|coil\s+material|emboliz(?:ed|ation)|treated|treatment|post-treatment)\b',
            clause,
            re.I
        ))
        has_residual_recurrent = bool(re.search(
            r'\b(?:residual\s+(?:(?:[\w-]+\s+){0,5}?(?:neck\s+|aneurysm\s+)?filling|(?:[\w-]+\s+){0,3}?aneurysm)|recurrent\s+(?:(?:[\w-]+\s+){0,5}?filling|(?:[\w-]+\s+){0,3}?aneurysm))\b',
            clause,
            re.I
        ))
        if has_treatment or has_residual_recurrent:
            # Clinician Round 2 Policy R2-Q1:
            # If imaging cannot assess the lumen (severe artifact obscuring recurrence), classify as NEI/manual review.
            is_inadequate_assessment = bool(re.search(
                r'\b(?:nondiagnostic|non-diagnostic|inadequate|cannot\s+be\s+(?:evaluated|assessed|determined)|obscured\s+by|artifact\s+obscuring|obscuring\s+(?:residual|recurrent|evaluation|assessment))\b',
                clause,
                re.I
            ))
            if is_inadequate_assessment:
                return TemporalityClass.AMBIGUOUS, [ReasonCode.LIMITED_EXAM_OR_COVERAGE]

            is_residual_negated = bool(re.search(
                r'\b(?:no|without|not|denies)\s+(?:definite\s+|current\s+)?(?:residual(?:\s+or\s+recurrent)?|recurrent)\b',
                clause,
                re.I
            ))
            if has_residual_recurrent and not is_residual_negated:
                if re.search(r'\b(?:possible|cannot\s+exclude|suspicious\s+for|concern\s+for)\b', clause, re.I):
                    return TemporalityClass.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]
                return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
            else:
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]

    # Label-policy overrides from YAML config
    if "chronic_present_state" in label_overrides:
        if has_local_chronic or has_local_old:
            if label_overrides["chronic_present_state"] == "H":
                return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
            elif label_overrides["chronic_present_state"] == "S":
                return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    found_classes = set()
    if has_local_regressing:
        found_classes.add(TemporalityClass.REGRESSING)
    if has_local_residual:
        found_classes.add(TemporalityClass.RESIDUAL)
    if has_local_chronic:
        found_classes.add(TemporalityClass.CHRONIC_CURRENT)
    if has_local_old:
        found_classes.add(TemporalityClass.HISTORICAL_ONLY)

    if len(found_classes) > 1:
        if found_classes == {TemporalityClass.RESIDUAL, TemporalityClass.CHRONIC_CURRENT}:
            return TemporalityClass.RESIDUAL, [ReasonCode.CURRENT_RESIDUAL_OR_SEQUELA]
        return TemporalityClass.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]

    if TemporalityClass.HISTORICAL_ONLY in found_classes:
        return TemporalityClass.HISTORICAL_ONLY, [ReasonCode.HISTORICAL_ONLY]
    if TemporalityClass.REGRESSING in found_classes:
        return TemporalityClass.REGRESSING, [ReasonCode.TEMPORAL_REGRESSION_NOT_RESOLUTION]
    if TemporalityClass.RESIDUAL in found_classes:
        return TemporalityClass.RESIDUAL, [ReasonCode.CURRENT_RESIDUAL_OR_SEQUELA]
    if TemporalityClass.CHRONIC_CURRENT in found_classes:
        return TemporalityClass.CHRONIC_CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]

    return TemporalityClass.CURRENT, [ReasonCode.ASSERT_DIRECT_CURRENT]
