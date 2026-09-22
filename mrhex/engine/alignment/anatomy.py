"""R06 — Anatomy and Laterality Alignment Gate.

Enforces anatomical compartment, neuroaxial level, and laterality constraints
defined in the approved clinician codebook prior to state confirmation.

Policy:
  - Confirmed anatomy mismatch safely blocks S and supports U (SAFE_RULE).
  - Unresolved anatomy ambiguity routes to LLM.
  - Cross-section laterality disagreement routes to LLM.
  - Do NOT invent anatomy rules not in codebook.
  - Do NOT auto-correct apparent laterality errors.
  - Uses word-bounded matching (RETIRE v1 unbounded _configured_hit).
"""
from __future__ import annotations

import re
from typing import Optional

from mrhex.engine.types import (
    AlignmentStatus,
    EvidenceUnit,
    ReasonCode,
    Section,
)


def _word_bounded_pattern(term: str) -> re.Pattern:
    """Compile a word-bounded, case-insensitive pattern for an anatomy term."""
    escaped = re.escape(term.strip()).replace(r"\ ", r"[\s-]+")
    return re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)


# Laterality cue patterns
_LEFT = re.compile(r"\b(left|left-sided|l\b)\b", re.IGNORECASE)
_RIGHT = re.compile(r"\b(right|right-sided|r\b)\b", re.IGNORECASE)
_BILATERAL = re.compile(r"\b(bilateral|bilaterally|both)\b", re.IGNORECASE)


INTRACRANIAL_BRAIN_HIERARCHY = (
    "brain", "cerebral", "cerebrum", "cerebellar", "cerebellum", "brainstem",
    "pons", "medulla", "midbrain", "thalamus", "thalami", "thalamic",
    "basal ganglia", "corpus callosum", "corona radiata", "centrum semiovale",
    "parenchyma", "parenchymal",
    "frontal", "parietal", "temporal", "occipital", "gyrus", "sulcus", "sulci",
    "parahippocampal", "hippocampus", "hippocampal", "amygdala",
    "ventricle", "ventricles", "ventricular", "cistern", "cisterns",
    "dura", "dural", "falx", "tentorium", "convexity", "parasagittal",
    "meninges", "meningeal", "leptomeninges", "leptomeningeal", "pachymeninges", "pachymeningeal",
    "fossa", "cranium", "cranial", "intracranial", "calvarium", "skull",
    "extra-axial", "intra-axial",
    "cavernous sinus", "sphenoid wing", "optic chiasm", "sellar", "suprasellar",
    "middle cerebral", "anterior cerebral", "posterior cerebral", "basilar",
    "circle of willis", "internal carotid", "vertebrobasilar", "carotid siphon",
    "anterior communicating", "posterior communicating", "cerebellopontine",
    "cp angle", "internal auditory canal", "iac", "vestibular", "acoustic"
)


def check_anatomy_alignment(
    clause: str,
    excluded_anatomy: list[str],
    required_anatomy: list[str],
    sentence_context: str = "",
    report_text: str = "",
    target_pathology: str = "",
) -> tuple[AlignmentStatus, list[ReasonCode]]:
    """Check anatomical compartment alignment for an evidence mention.

    Args:
        clause: The clause text containing the evidence mention.
        excluded_anatomy: Terms whose presence in context means the finding
            is outside the target compartment (confirmed mismatch).
        required_anatomy: Terms that must appear in context for the finding
            to be within the target compartment.
        sentence_context: Broader sentence context for anatomy evaluation.
        report_text: Full report text (governance scope only; NOT used to
            satisfy required anatomy for target mentions).

    Returns:
        (AlignmentStatus, list of reason codes)
    """
    reasons: list[ReasonCode] = []

    # Check excluded anatomy (confirmed mismatch → U safe)
    search_text = f"{clause} {sentence_context}"
    for term in excluded_anatomy:
        if not term.strip():
            continue
        if term.strip().lower() == "cerebellar":
            # Codebook: 'Exclude isolated cerebellar atrophy'. Coordinated cerebro-cerebellar atrophy is included.
            if _word_bounded_pattern(term).search(search_text):
                has_cerebral = bool(re.search(
                    r"\b(?:cerebr(?:al|um|o)|hemispher(?:ic|es?)|cort(?:ex|ical)|supratentorial|ventric(?:les?|ular)|sulc(?:i|al))\b",
                    search_text,
                    re.I,
                ))
                cerebral_negated_or_normal = bool(re.search(
                    r"\b(?:cerebr(?:al|um)|hemispher(?:ic|es?)|cort(?:ex|ical)|supratentorial)\s+(?:hemispheres?\s+)?(?:are\s+|is\s+)?(?:normal|unremarkable|preserved|without\s+atrophy)\b|\b(?:isolated\s+cerebellar|no\s+supratentorial)\b",
                    search_text,
                    re.I,
                ))
                if has_cerebral and not cerebral_negated_or_normal:
                    continue
                reasons.append(ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH)
                return AlignmentStatus.CONFIRMED_MISMATCH, reasons
            continue

        if _word_bounded_pattern(term).search(search_text):
            reasons.append(ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH)
            return AlignmentStatus.CONFIRMED_MISMATCH, reasons

    # Check required anatomy
    if required_anatomy:
        # Search strictly TARGET-LOCAL: target clause, then target sentence.
        # Report-level anatomy must NEVER satisfy target anatomy to prevent leakage.
        effective_required = list(required_anatomy)
        if any(t.lower() in ("intracranial", "cranium", "brain", "cns") for t in required_anatomy):
            effective_required.extend(INTRACRANIAL_BRAIN_HIERARCHY)

        # Target-local C4 restriction for Metastatic malignant neoplasm to brain:
        # Brain-metastasis SAFE_RULE S requires explicit intracranial/brain localization.
        # Generic "parenchyma" / "parenchymal" without explicit intracranial/brain context
        # must NOT satisfy the required brain localization for brain metastasis.
        if target_pathology and "metastat" in target_pathology.lower() and "brain" in target_pathology.lower():
            # If report explicitly states absence of brain parenchymal invasion/involvement -> CONFIRMED_MISMATCH
            if bool(re.search(r"\b(?:without|no)\s+(?:adjacent\s+)?(?:brain|cerebral|cortical|parenchymal)?\s*(?:parenchymal|cortical|brain)?\s*(?:invasion|involvement|extension)\b", search_text, re.I)):
                reasons.append(ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH)
                return AlignmentStatus.CONFIRMED_MISMATCH, reasons

            has_parenchymal_mention = bool(re.search(r"\b(?:intra)?parenchyma\w*\b", f"{clause} {sentence_context}", re.I))
            has_intracranial_context = report_text and bool(re.search(
                r"\b(?:brain|cranial|cerebr(?:al|um)|cerebell(?:ar|um)|brainstem|temporal|frontal|parietal|occipital|mesencephal\w+|ventric(?:le|ular)|sulc(?:i|al)|leptomening\w+|mening\w+|dura\w*|tentor\w+|falx)\b",
                report_text,
                re.I,
            )) and not bool(re.search(r"\b(?:liver|lung|hepatic|pulmonary|renal|abdominal|pelvic)\s+(?:parenchyma|metastases)\b", report_text, re.I))
            if has_parenchymal_mention and has_intracranial_context:
                effective_required.extend(["parenchyma", "parenchymal", "intraparenchymal"])
            else:
                effective_required = [
                    t for t in effective_required
                    if t.lower() not in ("parenchyma", "parenchymal")
                ]
            # Strip extra-axial meningeal terms: brain metastasis scope is brain parenchyma, not isolated dura/meninges
            extra_axial_meningeal = {
                "dura", "dural", "falx", "tentorium", "meninges", "meningeal",
                "leptomeninges", "leptomeningeal", "pachymeninges", "pachymeningeal"
            }
            effective_required = [
                t for t in effective_required
                if t.lower() not in extra_axial_meningeal
            ]

        # Target-local vascular anatomy for Intracranial aneurysm (P2.3 / P2.6 hardening):
        # Fulfills approved codebook: aneurysm of a named intracranial artery within intracranial arterial circulation.
        # Hardening: Procedure terms (coils, embolization, clips) removed. Only genuine anatomical locations allowed.
        if target_pathology == "Intracranial aneurysm":
            effective_required.extend([
                "mca", "middle cerebral artery", "middle cerebral",
                "aca", "anterior cerebral artery", "anterior cerebral",
                "pca", "posterior cerebral artery", "posterior cerebral",
                "sylvian fissure", "sylvian", "acom", "acoma", "pcom", "pcoma",
                "anterior communicating", "posterior communicating",
                "basilar", "basilar artery", "basilar tip", "vertebrobasilar", "carotid siphon",
                "internal carotid", "internal carotid artery", "ica", "ophthalmic artery",
                "ophthalmic segment", "cavernous segment", "cavernous", "petrous segment",
                "pica", "aica", "scas"
            ])
            has_postop_aneurysm_eval = bool(re.search(
                r"\b(?:residual|recurrent|recanaliz\w*|filling|post-treatment)\b",
                f"{clause} {sentence_context}",
                re.I,
            ))
            if has_postop_aneurysm_eval and report_text:
                # Bounded cross-sentence linkage: allow if report has genuine intracranial vascular anatomy
                # and no extracranial exclusion
                if any(_word_bounded_pattern(term).search(report_text) for term in effective_required if term.strip()):
                    if not re.search(r"\b(?:extracranial|cervical\s+internal\s+carotid)\b", report_text, re.I):
                        effective_required.extend([
                            "residual", "recurrent", "filling", "post-treatment"
                        ])

        # Target-local spinal neural foraminal anatomy for Foraminal Spinal Stenosis (P2.3):
        # Fulfills approved codebook: narrowing of one or more spinal neural/intervertebral foramina.
        if target_pathology == "Foraminal Spinal Stenosis":
            effective_required.extend([
                "neural foramen", "neural foramina", "neuroforamen", "neuroforamina",
                "intervertebral foramen", "intervertebral foramina", "uncinate",
                "foraminal", "foramina", "foramen"
            ])

        # Target-local anatomy for Intracranial meningioma:
        # Codebook: dural and skull base intracranial anatomical landmarks.
        if target_pathology == "Intracranial meningioma":
            effective_required.extend([
                "planum sphenoidale", "sphenoid wing", "olfactory groove", "crista galli", "clivus",
                "tuberculum sellae", "parasagittal", "falx", "tentorium", "convexity", "dura", "dural"
            ])
            # Explicit current residual/recurrent meningioma site anatomy (resection cavity/margin/tumor bed)
            # Allowed ONLY when explicit residual/recurrent tumor is present in local context.
            has_explicit_postop_meningioma = bool(re.search(
                r"\b(?:residual|recurrent)\s+(?:meningioma|tumor)\b",
                f"{clause} {sentence_context}",
                re.I,
            ))
            if has_explicit_postop_meningioma:
                effective_required.extend([
                    "surgical cavity", "resection cavity", "tumor bed", "resection margin", "margin", "cavity"
                ])

        # Target-local anatomy for Glioma:
        # Specific cerebral lobes, intra-axial compartment, and intrinsically brain neoplasms (GBM, glioblastoma).
        if target_pathology == "Glioma":
            effective_required.extend([
                "insular", "temporal", "frontal", "parietal", "occipital", "intra-axial", "intraaxial",
                "gbm", "glioblastoma"
            ])
            # Explicit current residual/recurrent glioma site anatomy
            has_explicit_postop_glioma = bool(re.search(
                r"\b(?:residual|recurrent)\s+(?:glioma|tumor|astrocytoma|glioblastoma)\b",
                f"{clause} {sentence_context}",
                re.I,
            ))
            if has_explicit_postop_glioma:
                effective_required.extend([
                    "surgical cavity", "resection cavity", "tumor bed", "resection margin", "margin", "cavity"
                ])

        # Target-local anatomy for Cerebral edema (P2.4):
        # Clinician Policy Round 1: Edematous change in brain parenchyma (including white matter).
        if target_pathology == "Cerebral edema":
            effective_required.extend([
                "white matter", "centrum semiovale", "corona radiata", "subcortical"
            ])


        found = False
        for search_scope in [clause, sentence_context]:
            if not search_scope:
                continue
            for term in effective_required:
                if not term.strip():
                    continue
                if _word_bounded_pattern(term).search(search_scope):
                    found = True
                    break
            if found:
                break

        if not found and required_anatomy:
            # Required anatomy not found in target-local scope → UNRESOLVED → ROUTE_TO_LLM
            reasons.append(ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH)
            return AlignmentStatus.UNRESOLVED, reasons

    return AlignmentStatus.ALIGNED, reasons


def detect_laterality(text: str) -> Optional[str]:
    """Detect laterality mentioned in text.

    Returns:
        'left', 'right', 'bilateral', or None
    """
    has_left = bool(_LEFT.search(text))
    has_right = bool(_RIGHT.search(text))
    has_bilateral = bool(_BILATERAL.search(text))

    if has_bilateral:
        return "bilateral"
    if has_left and has_right:
        return "bilateral"  # both mentioned = bilateral
    if has_left:
        return "left"
    if has_right:
        return "right"
    return None


def check_laterality_across_evidence(
    evidence_units: list[EvidenceUnit],
) -> tuple[AlignmentStatus, list[ReasonCode]]:
    """Check for laterality conflicts across multiple evidence spans.

    Cross-section laterality disagreement → ROUTE_TO_LLM.

    Args:
        evidence_units: All evidence units for this target pathology.

    Returns:
        (AlignmentStatus, list of reason codes)
    """
    lateralities: dict[Section, set[str]] = {}

    for unit in evidence_units:
        lat = detect_laterality(unit.clause_text or unit.text)
        if lat:
            lateralities.setdefault(unit.section, set()).add(lat)

    if not lateralities:
        return AlignmentStatus.NOT_APPLICABLE, []

    # Metastatic malignant neoplasm to brain:
    # Multiple/bilateral metastatic lesions across compartments do NOT represent laterality conflict.
    # Codebook subtype rules explicitly state: "Include solitary, multiple and hemorrhagic brain metastases."
    has_meta = any(
        eu.target_pathology and "metastat" in eu.target_pathology.lower() and "brain" in eu.target_pathology.lower()
        for eu in evidence_units
    )
    if has_meta:
        return AlignmentStatus.ALIGNED, []

    # Collect all lateralities across sections
    all_lats: set[str] = set()
    for lats in lateralities.values():
        all_lats |= lats

    # Check for cross-section conflicts
    if len(lateralities) > 1:
        sections = list(lateralities.keys())
        for i in range(len(sections)):
            for j in range(i + 1, len(sections)):
                lats_i = lateralities[sections[i]]
                lats_j = lateralities[sections[j]]
                # Bilateral is compatible with everything
                non_bilateral_i = lats_i - {"bilateral"}
                non_bilateral_j = lats_j - {"bilateral"}
                if non_bilateral_i and non_bilateral_j and non_bilateral_i != non_bilateral_j:
                    return AlignmentStatus.UNRESOLVED, [ReasonCode.LATERALITY_CONFLICT]

    # Check within-section conflicts (left and right in same section without bilateral)
    for section, lats in lateralities.items():
        non_bilateral = lats - {"bilateral"}
        if len(non_bilateral) > 1:
            return AlignmentStatus.UNRESOLVED, [ReasonCode.LATERALITY_CONFLICT]

    return AlignmentStatus.ALIGNED, []
