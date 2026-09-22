"""Deterministic Fallback Resolver for D2-STANDALONE.

Resolves routed cases (ROUTE_TO_LLM from selective D2) into exactly one
MR-RATE state: S, U, C, UC, H, or NEI.

Strictly deterministic: zero API, LLM, or external model calls.
Follows the 7-step MR-RATE hierarchy (Steps A through G) and multi-evidence
reconciliation principles.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from mrhex.engine.types import (
    AlignmentStatus,
    AssertionPolarity,
    CertaintyLevel,
    EvidenceState,
    EvidenceUnit,
    ReasonCode,
    Section,
    TemporalityClass,
)
from mrhex.engine.retrieval.matcher import extract_evidence
from mrhex.engine.segmentation.sentences import sentence_for_offset
from mrhex.engine.segmentation.clauses import clause_for_offset, is_coordination_ambiguous
from mrhex.engine.assertion.negation import analyze_negation
from mrhex.engine.assertion.hedging import analyze_hedging
from mrhex.engine.assertion.temporality import analyze_temporality
from mrhex.engine.alignment.anatomy import check_anatomy_alignment
from mrhex.engine.alignment.subtype import (
    check_lineage_established,
    check_lineage_unestablished,
    check_subtype_alignment,
)
from mrhex.engine.aggregation.fallback import (
    SEVERE_LIMITATION_PATTERNS,
    PARTIAL_LIMITATION_PATTERNS,
)
from mrhex.config import load_v2_entry_for_label
from mrhex.rules.atrophy import evaluate_cerebral_atrophy_standalone
from mrhex.rules.gliosis import evaluate_gliosis_standalone
from mrhex.rules.encephalomalacia import evaluate_encephalomalacia_standalone
from mrhex.rules.demyelinating import evaluate_demyelinating_standalone
from mrhex.rules.aneurysm import evaluate_aneurysm_standalone
from mrhex.rules.empty_sella import evaluate_empty_sella_standalone
from mrhex.rules.hyperostosis import evaluate_hyperostosis_standalone
from mrhex.rules.cerebral_edema import evaluate_cerebral_edema_standalone
from mrhex.rules.microhemorrhage import evaluate_microhemorrhage_standalone
from mrhex.rules.glioma import evaluate_glioma_standalone
from mrhex.rules.pituitary_adenoma import evaluate_pituitary_adenoma_standalone
from mrhex.rules.meningioma import evaluate_meningioma_standalone
from mrhex.rules.pineal_cyst import evaluate_pineal_cyst_standalone
from mrhex.rules.lacunar_infarct import evaluate_lacunar_infarct_standalone
from mrhex.rules.cerebellar_degeneration import evaluate_cerebellar_degeneration_standalone
from mrhex.rules.spinal_stenosis import evaluate_spinal_stenosis_standalone
from mrhex.rules.spinal_cord_compression import evaluate_spinal_cord_compression_standalone
from mrhex.rules.subdural_hemorrhage import evaluate_subdural_hemorrhage_standalone
from mrhex.rules.watershed_infarct import evaluate_watershed_infarct_standalone
from mrhex.rules.chiari_malformation import evaluate_chiari_malformation_standalone
from mrhex.rules.vertebral_hemangioma import evaluate_vertebral_hemangioma_standalone
from mrhex.rules.choroid_plexus_cyst import evaluate_choroid_plexus_cyst_standalone
from mrhex.rules.cavernous_hemangioma import evaluate_cavernous_hemangioma_standalone
from mrhex.rules.mega_cisterna_magna import evaluate_mega_cisterna_magna_standalone
from mrhex.rules.herniation_nucleus_pulposus import evaluate_herniation_nucleus_pulposus_standalone
from mrhex.rules.foraminal_stenosis import evaluate_foraminal_stenosis_standalone
from mrhex.rules.schwannoma import evaluate_schwannoma_standalone
from mrhex.rules.rathke_pouch_cyst import evaluate_rathke_pouch_cyst_standalone
from mrhex.rules.arachnoid_cyst import evaluate_arachnoid_cyst_standalone
from mrhex.rules.chronic_mastoiditis import evaluate_chronic_mastoiditis_standalone

# Patterns for Candidate #27 (Brain metastasis)
C27_EXPLICIT_FORMS = [
    "metastatic brain lesion",
    "metastatic brain lesions",
    "metastatic tumor to brain",
    "secondary brain tumor",
    "secondary malignant brain lesion",
    "secondary malignant brain lesions",
    "cerebral metastasis",
    "cerebral metastases",
    "intracranial metastasis",
    "intracranial metastases",
]

# Exclusionary negation patterns (negation of other/additional lesions does not negate an affirmed lesion)
EXCLUSIONARY_NEGATION_RE = re.compile(
    r"\b(?:apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than|"
    r"no\s+other|no\s+additional|no\s+further|no\s+new|no\s+different)\b",
    re.I,
)

# Recurrence / residual absence patterns (historical target present, but no current recurrence)
NO_RECURRENCE_RE = re.compile(
    r"\b(?:no\s+(?:evidence\s+of\s+)?(?:recurrence|residual|recurrent\s+(?:tumor|mass|lesion)|residual\s+(?:tumor|mass|lesion))|"
    r"without\s+(?:evidence\s+of\s+)?(?:recurrence|residual))\b",
    re.I,
)

# Indication only cues (when target is only an indication/reason for exam, not a documented past history)
INDICATION_ONLY_RE = re.compile(
    r"\b(?:indication|clinical\s+information|reason\s+for\s+exam|preliminary\s+diagnosis|"
    r"r/o|rule\s+out|evaluate\s+for|suspected\s+by\s+clinician)\b",
    re.I,
)

# Past medical history cues (explicit past history)
PAST_HISTORY_RE = re.compile(
    r"\b(?:history\s+of|hx\s+of|known|prior|remote|previously\s+diagnosed|status\s+post|s/p|operated|resected)\b",
    re.I,
)

SPECIALIZED_FALLBACK_PATHOLOGIES = (
    "Silent micro-hemorrhage of brain",
    "Glioma",
    "Pituitary adenoma",
    "Intracranial meningioma",
    "Cyst of pineal gland",
    "Lacunar infarct",
    "Cerebellar degeneration",
    "Spinal stenosis",
    "Spinal cord compression",
    "Subdural intracranial hemorrhage",
    "Watershed infarct",
    "Choroid plexus cyst",
    "Cavernous hemangioma",
    "Mega cisterna magna",
    "Herniation of nucleus pulposus",
    "Foraminal Spinal Stenosis",
    "Schwannoma",
    "Rathke's pouch cyst",
    "Arachnoid cyst",
    "Chronic mastoiditis",
)


def _evaluate_pathology_specific_standalone_fallback(
    target_pathology: str,
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for optimized pathologies."""
    if target_pathology == "Arachnoid cyst":
        return evaluate_arachnoid_cyst_standalone(text, case_id=case_id)
    if target_pathology == "Chronic mastoiditis":
        return evaluate_chronic_mastoiditis_standalone(text, case_id=case_id)
    if target_pathology == "Chiari malformation":
        return evaluate_chiari_malformation_standalone(text, case_id=case_id)
    if target_pathology == "Hemangioma of vertebral column":
        return evaluate_vertebral_hemangioma_standalone(text, case_id=case_id)
    if target_pathology == "Choroid plexus cyst":
        return evaluate_choroid_plexus_cyst_standalone(text, case_id=case_id)
    if target_pathology == "Cavernous hemangioma":
        return evaluate_cavernous_hemangioma_standalone(text, case_id=case_id)
    if target_pathology == "Mega cisterna magna":
        return evaluate_mega_cisterna_magna_standalone(text, case_id=case_id)
    if target_pathology == "Herniation of nucleus pulposus":
        return evaluate_herniation_nucleus_pulposus_standalone(text, case_id=case_id)
    if target_pathology == "Foraminal Spinal Stenosis":
        return evaluate_foraminal_stenosis_standalone(text, case_id=case_id)
    if target_pathology == "Schwannoma":
        return evaluate_schwannoma_standalone(text, case_id=case_id)
    if target_pathology == "Rathke's pouch cyst":
        return evaluate_rathke_pouch_cyst_standalone(text, case_id=case_id)
    if target_pathology == "Cerebral atrophy":
        return evaluate_cerebral_atrophy_standalone(text, case_id=case_id)
    if target_pathology == "Gliosis":
        return evaluate_gliosis_standalone(text, case_id=case_id)
    if target_pathology == "Encephalomalacia":
        return evaluate_encephalomalacia_standalone(text, case_id=case_id)
    if target_pathology == "Demyelinating disease of central nervous system":
        return evaluate_demyelinating_standalone(text, case_id=case_id)
    if target_pathology == "Intracranial aneurysm":
        return evaluate_aneurysm_standalone(text, case_id=case_id)
    if target_pathology == "Empty sella syndrome":
        return evaluate_empty_sella_standalone(text, case_id=case_id)
    if target_pathology == "Hyperostosis of skull":
        return evaluate_hyperostosis_standalone(text, case_id=case_id)
    if target_pathology == "Cerebral edema":
        return evaluate_cerebral_edema_standalone(text, case_id=case_id)
    if target_pathology == "Silent micro-hemorrhage of brain":
        return evaluate_microhemorrhage_standalone(text, case_id=case_id)
    if target_pathology == "Glioma":
        return evaluate_glioma_standalone(text, case_id=case_id)
    if target_pathology == "Pituitary adenoma":
        return evaluate_pituitary_adenoma_standalone(text, case_id=case_id)
    if target_pathology == "Intracranial meningioma":
        return evaluate_meningioma_standalone(text, case_id=case_id)
    if target_pathology == "Cyst of pineal gland":
        return evaluate_pineal_cyst_standalone(text, case_id=case_id)
    if target_pathology == "Lacunar infarct":
        return evaluate_lacunar_infarct_standalone(text, case_id=case_id)
    if target_pathology == "Cerebellar degeneration":
        return evaluate_cerebellar_degeneration_standalone(text, case_id=case_id)
    if target_pathology == "Spinal stenosis":
        return evaluate_spinal_stenosis_standalone(text, case_id=case_id)
    if target_pathology == "Spinal cord compression":
        return evaluate_spinal_cord_compression_standalone(text, case_id=case_id)
    if target_pathology == "Subdural intracranial hemorrhage":
        return evaluate_subdural_hemorrhage_standalone(text, case_id=case_id)
    if target_pathology == "Watershed infarct":
        return evaluate_watershed_infarct_standalone(text, case_id=case_id)
    return None


_CACHED_C27_ENTRY: dict[str, Any] | None = None


def _get_candidate_27_entry() -> dict[str, Any]:
    """Build and cache the Candidate #27 entry with approved surface forms."""
    global _CACHED_C27_ENTRY
    if _CACHED_C27_ENTRY is None:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        codebook_path = root / "configs/final_pathology_codebook.yaml"
        base_rules_path = root / "configs/final_deterministic_rules_v2.yaml"
        entry = load_v2_entry_for_label(
            codebook_path,
            base_rules_path,
            "Metastatic malignant neoplasm to brain",
        )
        entry["machine_rules"]["scope_policy"] = {
            "enabled": True,
            "presence_semantics": "ANY_IN_SCOPE",
        }
        entry["machine_rules"]["surface_forms"] = list(
            entry["machine_rules"].get("surface_forms", [])
        ) + C27_EXPLICIT_FORMS
        _CACHED_C27_ENTRY = entry
    return _CACHED_C27_ENTRY


def extract_and_analyze_units_for_candidate27(
    text: str,
    source_mode: str = "full_report",
) -> list[EvidenceUnit]:
    """Extract and analyze evidence units specifically for Candidate #27."""
    c27_entry = _get_candidate_27_entry()
    target_pathology = "Metastatic malignant neoplasm to brain"
    units = extract_evidence(text, c27_entry, target_pathology, source_mode=source_mode)
    if not units:
        return []

    machine = c27_entry.get("machine_rules", {})
    chronicity = str(machine.get("required_chronicity", ""))
    assertion_target_terms = tuple(
        str(term)
        for term in (
            list(machine.get("positive_terms", []))
            + list(machine.get("surface_forms", []))
            + [target_pathology]
        )
        if str(term).strip()
    )

    for eu in units:
        sent_text, sent_start, sent_end = sentence_for_offset(text, eu.start)
        eu.sentence_text = sent_text
        eu.sentence_start = sent_start
        eu.sentence_end = sent_end

        clause_text, clause_start, clause_end = clause_for_offset(
            sent_text, sent_start, eu.start
        )
        eu.clause_text = clause_text
        eu.clause_start = clause_start
        eu.clause_end = clause_end

        target_in_sent_start = eu.start - sent_start
        target_in_sent_end = eu.end - sent_start
        if is_coordination_ambiguous(sent_text, target_in_sent_start, target_in_sent_end):
            eu.reason_codes.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)

        target_in_clause = eu.start - clause_start
        target_end_in_clause = eu.end - clause_start

        label_overrides = machine.get("label_policy_overrides", {})
        global_overrides = machine.get("global_policy_overrides", {})
        temp_class, temp_reasons = analyze_temporality(
            clause_text,
            eu.section,
            target_in_clause,
            target_end_in_clause,
            target_pathology=target_pathology,
            label_overrides=label_overrides,
            global_overrides=global_overrides,
        )
        eu.temporality = temp_class
        eu.reason_codes.extend(temp_reasons)

        polarity, neg_reasons = analyze_negation(
            clause_text,
            target_in_clause,
            target_end_in_clause,
            eu.matched_term,
            chronicity_constraint=chronicity,
        )
        eu.assertion_polarity = polarity
        eu.reason_codes.extend(neg_reasons)

        if polarity != AssertionPolarity.NEGATED:
            certainty, hedge_reasons = analyze_hedging(
                clause_text,
                target_in_clause,
                target_end_in_clause,
                eu.matched_term,
                global_overrides=global_overrides,
                target_pathology=target_pathology,
                target_terms=assertion_target_terms,
            )
            eu.certainty = certainty
            eu.reason_codes.extend(hedge_reasons)

        # Anatomy alignment
        excluded_anatomy = machine.get("excluded_anatomy", [])
        required_anatomy = machine.get("required_anatomy", [])
        anat_status, anat_reasons = check_anatomy_alignment(
            eu.clause_text,
            excluded_anatomy,
            required_anatomy,
            sentence_context=eu.sentence_text,
            report_text=text,
            target_pathology=target_pathology,
        )
        eu.anatomy_status = anat_status
        eu.reason_codes.extend(anat_reasons)

    return units


def resolve_deterministic_fallback(
    report: object,
    entry: Mapping[str, Any],
    d2_res: Mapping[str, Any],
    *,
    case_id: str = "",
    source_mode: str = "full_report",
) -> dict[str, Any]:
    """Execute the deterministic fallback resolver on a routed D2 case.

    Implements Steps A through G of the deterministic fallback hierarchy:
      Step A: Assess report sufficiency (empty/unusable -> NEI)
      Step B: Identify current affirmative evidence (definite current -> S)
      Step C: Identify current uncertain evidence (genuine hedging -> UC)
      Step D: Historical-only evidence (past/treated only -> H)
      Step E: Explicit current contradiction (negated only -> C)
      Step F: Adequate report with no target evidence (target not found -> U)
      Step G: Irreconcilable remaining case (unresolved conflict -> NEI)

    Returns:
      Dictionary containing:
        - standalone_state: Exactly one of S, U, C, UC, H, NEI
        - fallback_rule_id: Deterministic fallback rule ID
        - reason_code: Primary reason code string
        - reason_codes: List of all reason codes
        - evidence_spans: Formatted evidence spans
    """
    text = "" if report is None else str(report)
    clean_text = text.strip()
    target_pathology = str(entry.get("label", entry.get("canonical_name", "")))

    # -------------------------------------------------------------------------
    # STEP A: Assess report sufficiency
    # -------------------------------------------------------------------------
    if not clean_text:
        return {
            "standalone_state": EvidenceState.NEI.value,
            "fallback_rule_id": "FALLBACK_A_EMPTY_REPORT",
            "reason_code": ReasonCode.LIMITED_EXAM_OR_COVERAGE.value,
            "reason_codes": [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value, "EMPTY_REPORT"],
            "evidence_spans": [],
        }

    # Severe explicit technical limitation rendering exam uninterpretable
    if any(p.search(clean_text) for p in SEVERE_LIMITATION_PATTERNS):
        return {
            "standalone_state": EvidenceState.NEI.value,
            "fallback_rule_id": "FALLBACK_A_SEVERE_LIMITATION",
            "reason_code": ReasonCode.LIMITED_EXAM_OR_COVERAGE.value,
            "reason_codes": [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value, "UNINTERPRETABLE_EXAMINATION"],
            "evidence_spans": [],
        }

    # -------------------------------------------------------------------------
    # Retrieve evidence spans / units
    # -------------------------------------------------------------------------
    spans: list[dict[str, Any]] = []

    if target_pathology == "Metastatic malignant neoplasm to brain":
        # Candidate #27: Use full Candidate 27 extraction and assertion pipeline
        c27_units = extract_and_analyze_units_for_candidate27(text, source_mode=source_mode)
        for eu in c27_units:
            # Filter out confirmed anatomy mismatches (e.g. spine/liver/calvarium only)
            if eu.anatomy_status == AlignmentStatus.CONFIRMED_MISMATCH:
                continue
            spans.append({
                "text": eu.clause_text or eu.matched_term,
                "start": eu.start,
                "end": eu.end,
                "section": eu.section.value if hasattr(eu.section, "value") else str(eu.section),
                "polarity": eu.assertion_polarity.value if hasattr(eu.assertion_polarity, "value") else str(eu.assertion_polarity),
                "matched_term": eu.matched_term,
                "certainty": eu.certainty.value if hasattr(eu.certainty, "value") else str(eu.certainty),
                "temporality": eu.temporality.value if hasattr(eu.temporality, "value") else str(eu.temporality),
                "clause_text": eu.clause_text or "",
                "sentence_text": eu.sentence_text or "",
            })
    else:
        # Use existing evidence spans from D2 output
        raw_spans = d2_res.get("evidence_spans", [])
        for sp in raw_spans:
            # Reconstruct clause_text / sentence_text if missing
            start = sp.get("start", 0)
            end = sp.get("end", 0)
            sent_text, s_start, s_end = sentence_for_offset(text, start)
            cl_text, _, _ = clause_for_offset(sent_text, s_start, start)
            sp_copy = dict(sp)
            sp_copy["clause_text"] = cl_text
            sp_copy["sentence_text"] = sent_text
            spans.append(sp_copy)

    # -------------------------------------------------------------------------
    # If NO target evidence spans exist in an adequate report:
    # -------------------------------------------------------------------------
    if not spans:
        # Check if partial limitation pattern coexists
        if any(p.search(clean_text) for p in PARTIAL_LIMITATION_PATTERNS) and not any(
            sec in text.lower() for sec in ["impression:", "findings:", "sonuç:", "bulgular:"]
        ):
            return {
                "standalone_state": EvidenceState.NEI.value,
                "fallback_rule_id": "FALLBACK_A_PARTIAL_LIMITATION_NO_REPORT",
                "reason_code": ReasonCode.LIMITED_EXAM_OR_COVERAGE.value,
                "reason_codes": [ReasonCode.LIMITED_EXAM_OR_COVERAGE.value],
                "evidence_spans": [],
            }

        # Check pathology-specific standalone candidate rules for Cerebral atrophy & Gliosis
        pathology_res = _evaluate_pathology_specific_standalone_fallback(
            target_pathology, clean_text, case_id=case_id
        )
        if pathology_res is not None:
            return pathology_res

        # Step F: Adequate report with no target evidence -> U
        return {
            "standalone_state": EvidenceState.U.value,
            "fallback_rule_id": "FALLBACK_F_NO_MATCH_U",
            "reason_code": ReasonCode.TARGET_RETRIEVAL_INCOMPLETE.value,
            "reason_codes": [ReasonCode.TARGET_RETRIEVAL_INCOMPLETE.value, "TARGET_NOT_FOUND_IN_ADEQUATE_REPORT"],
            "evidence_spans": [],
        }

    # -------------------------------------------------------------------------
    # Analyze evidence spans by section, temporality, polarity, and certainty
    # -------------------------------------------------------------------------
    radiologic_spans = [
        sp for sp in spans
        if sp.get("section") in ("FINDINGS", "IMPRESSION", "OTHER")
    ]
    clinical_spans = [
        sp for sp in spans
        if sp.get("section") == "CLINICAL_HISTORY"
    ]

    # If radiologic spans exist, they supersede clinical history/indication
    active_spans = radiologic_spans if radiologic_spans else clinical_spans

    # If ONLY clinical spans exist:
    if not radiologic_spans and clinical_spans:
        if target_pathology in SPECIALIZED_FALLBACK_PATHOLOGIES:
            pathology_res = _evaluate_pathology_specific_standalone_fallback(
                target_pathology, clean_text, case_id=case_id
            )
            if pathology_res is not None:
                return pathology_res

        # Check if clinical span is an explicit past medical history or mere indication/question
        all_clinical_text = " ".join(sp.get("sentence_text", "") for sp in clinical_spans)
        is_past_history = bool(PAST_HISTORY_RE.search(all_clinical_text))
        is_indication = bool(INDICATION_ONLY_RE.search(all_clinical_text))

        if is_past_history and not is_indication:
            # Documented past medical history without current radiologic active disease -> H
            return {
                "standalone_state": EvidenceState.H.value,
                "fallback_rule_id": "FALLBACK_D_CLINICAL_HISTORY_ONLY_H",
                "reason_code": ReasonCode.HISTORICAL_ONLY.value,
                "reason_codes": [ReasonCode.HISTORICAL_ONLY.value, "CLINICAL_HISTORY_ONLY"],
                "evidence_spans": spans,
            }
        else:
            # Clinical indication / question unconfirmed by imaging -> U
            return {
                "standalone_state": EvidenceState.U.value,
                "fallback_rule_id": "FALLBACK_F_CLINICAL_INDICATION_UNSUPPORTED_U",
                "reason_code": ReasonCode.CLINICAL_ONLY_PROVENANCE.value,
                "reason_codes": [ReasonCode.CLINICAL_ONLY_PROVENANCE.value, "CLINICAL_INDICATION_UNSUPPORTED"],
                "evidence_spans": spans,
            }

    # Group radiologic spans into assertion categories
    current_affirmative_spans = []
    current_uncertain_spans = []
    historical_spans = []
    negated_spans = []
    ambiguous_spans = []

    for sp in active_spans:
        pol = sp.get("polarity", "AFFIRMED")
        temp = sp.get("temporality", "CURRENT")
        cert = sp.get("certainty", "DEFINITE")
        cl = sp.get("clause_text", "")

        if pol == "NEGATED":
            negated_spans.append(sp)
        elif pol == "AMBIGUOUS" or temp == "AMBIGUOUS":
            ambiguous_spans.append(sp)
        elif temp in ("HISTORICAL_ONLY", "RESOLVED"):
            historical_spans.append(sp)
        elif cert in ("HEDGED", "DIFFERENTIAL"):
            current_uncertain_spans.append(sp)
        elif pol in ("AFFIRMED", "NEGATED_MODIFIER"):
            current_affirmative_spans.append(sp)
        else:
            ambiguous_spans.append(sp)

    # -------------------------------------------------------------------------
    # MULTI-EVIDENCE RECONCILIATION
    # -------------------------------------------------------------------------

    # 1. Current positive + Current negative reconciliation
    if current_affirmative_spans and negated_spans:
        # Check if negated spans are exclusionary scoping (e.g. "no other metastasis", "apart from X, no lesion")
        is_exclusionary = all(
            bool(EXCLUSIONARY_NEGATION_RE.search(sp.get("clause_text", "")))
            or bool(re.search(r'\b(?:other|additional|further|new)\b', sp.get("clause_text", ""), re.I))
            for sp in negated_spans
        )
        # Check if negated spans are absence of recurrence of a different/treated lesion
        is_no_recurrence = all(
            bool(NO_RECURRENCE_RE.search(sp.get("clause_text", "")))
            for sp in negated_spans
        )
        # Check cross-section resolution (Impression affirms finding)
        impression_affirmative = any(sp.get("section") == "IMPRESSION" for sp in current_affirmative_spans)
        findings_only_negation = all(sp.get("section") == "FINDINGS" for sp in negated_spans)

        if is_exclusionary or is_no_recurrence or (impression_affirmative and findings_only_negation):
            # Affirmed current lesion stands
            negated_spans = []
        else:
            # Check if Impression negates while Findings had affirmative (Impression overrides)
            impression_negated = any(sp.get("section") == "IMPRESSION" for sp in negated_spans)
            findings_only_affirmative = all(sp.get("section") == "FINDINGS" for sp in current_affirmative_spans)
            if impression_negated and findings_only_affirmative:
                current_affirmative_spans = []
            else:
                if target_pathology in ("Empty sella syndrome", "Hyperostosis of skull", "Cerebral edema", *SPECIALIZED_FALLBACK_PATHOLOGIES):
                    path_res = _evaluate_pathology_specific_standalone_fallback(target_pathology, clean_text, case_id=case_id)
                    if path_res is not None:
                        return path_res
                # Direct irreconcilable conflict in same target finding -> NEI (Step G)
                return {
                    "standalone_state": EvidenceState.NEI.value,
                    "fallback_rule_id": "FALLBACK_G_UNRESOLVED_CONFLICT_NEI",
                    "reason_code": ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT.value,
                    "reason_codes": [ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT.value, "IRRECONCILABLE_POLARITY_CONFLICT"],
                    "evidence_spans": spans,
                }

    # 2. Historical target + explicit no current recurrence/residual
    # -> normally H because the target is established historically but not currently active.
    if historical_spans and negated_spans and not current_affirmative_spans and not current_uncertain_spans:
        return {
            "standalone_state": EvidenceState.H.value,
            "fallback_rule_id": "FALLBACK_D_HISTORICAL_WITH_NO_RECURRENCE_H",
            "reason_code": ReasonCode.HISTORICAL_ONLY.value,
            "reason_codes": [ReasonCode.HISTORICAL_ONLY.value, "HISTORICAL_TARGET_NO_CURRENT_RECURRENCE"],
            "evidence_spans": spans,
        }

    # Pathologies with specialized affirmative/uncertain/historical disambiguation
    if target_pathology in SPECIALIZED_FALLBACK_PATHOLOGIES:
        pathology_res = _evaluate_pathology_specific_standalone_fallback(
            target_pathology, clean_text, case_id=case_id
        )
        if pathology_res is not None:
            return pathology_res

    # -------------------------------------------------------------------------
    # STEP B: Identify current affirmative evidence
    # -------------------------------------------------------------------------
    if current_affirmative_spans:
        # Current positive + historical positive -> S (current evidence establishes present disease)
        return {
            "standalone_state": EvidenceState.S.value,
            "fallback_rule_id": "FALLBACK_B_CURRENT_AFFIRMATIVE_S",
            "reason_code": ReasonCode.ASSERT_DIRECT_CURRENT.value,
            "reason_codes": [ReasonCode.ASSERT_DIRECT_CURRENT.value],
            "evidence_spans": spans,
        }

    # -------------------------------------------------------------------------
    # STEP C: Identify current uncertain evidence
    # -------------------------------------------------------------------------
    if current_uncertain_spans:
        # Current uncertain + historical positive -> use current status (UC)
        return {
            "standalone_state": EvidenceState.UC.value,
            "fallback_rule_id": "FALLBACK_C_CURRENT_UNCERTAIN_UC",
            "reason_code": ReasonCode.ASSERT_HEDGED.value,
            "reason_codes": [ReasonCode.ASSERT_HEDGED.value],
            "evidence_spans": spans,
        }

    # -------------------------------------------------------------------------
    # STEP D: Historical-only evidence
    # -------------------------------------------------------------------------
    if historical_spans:
        return {
            "standalone_state": EvidenceState.H.value,
            "fallback_rule_id": "FALLBACK_D_HISTORICAL_ONLY_H",
            "reason_code": ReasonCode.HISTORICAL_ONLY.value,
            "reason_codes": [ReasonCode.HISTORICAL_ONLY.value],
            "evidence_spans": spans,
        }

    # -------------------------------------------------------------------------
    # STEP E: Explicit current contradiction
    # -------------------------------------------------------------------------
    if negated_spans:
        return {
            "standalone_state": EvidenceState.C.value,
            "fallback_rule_id": "FALLBACK_E_EXPLICIT_CONTRADICTION_C",
            "reason_code": ReasonCode.ASSERT_TARGET_NEGATED.value,
            "reason_codes": [ReasonCode.ASSERT_TARGET_NEGATED.value],
            "evidence_spans": spans,
        }

    # -------------------------------------------------------------------------
    # STEP F / G: Ambiguous or remaining irreconcilable cases
    # -------------------------------------------------------------------------
    # Check pathology-specific rules for Silent micro-hemorrhage and Glioma before generic ambiguous scope NEI
    if target_pathology in SPECIALIZED_FALLBACK_PATHOLOGIES:
        pathology_res = _evaluate_pathology_specific_standalone_fallback(
            target_pathology, clean_text, case_id=case_id
        )
        if pathology_res is not None:
            return pathology_res

    if ambiguous_spans:
        # Severe ambiguity preventing assignment
        return {
            "standalone_state": EvidenceState.NEI.value,
            "fallback_rule_id": "FALLBACK_G_AMBIGUOUS_SCOPE_NEI",
            "reason_code": ReasonCode.MALFORMED_OR_COMPLEX_SCOPE.value,
            "reason_codes": [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE.value, "AMBIGUOUS_EVIDENCE_SCOPE"],
            "evidence_spans": spans,
        }

    # Check pathology-specific standalone candidate rules for Cerebral atrophy & Gliosis
    pathology_res = _evaluate_pathology_specific_standalone_fallback(
        target_pathology, clean_text, case_id=case_id
    )
    if pathology_res is not None:
        return pathology_res

    # Default fallback for adequate report without affirmative/negative finding
    return {
        "standalone_state": EvidenceState.U.value,
        "fallback_rule_id": "FALLBACK_F_DEFAULT_UNSUPPORTED_U",
        "reason_code": ReasonCode.TARGET_RETRIEVAL_INCOMPLETE.value,
        "reason_codes": [ReasonCode.TARGET_RETRIEVAL_INCOMPLETE.value],
        "evidence_spans": spans,
    }
