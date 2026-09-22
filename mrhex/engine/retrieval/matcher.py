import re
from mrhex.engine.types import EvidenceUnit
from mrhex.engine.matching.patterns import find_all_matches
from mrhex.engine.retrieval.sections import section_for_offsets
from mrhex.engine.retrieval.vocabulary import terms_for_entry

def is_metastatic_origin_established(text: str) -> bool:
    """Clinician Round 3 Policy: Check whether report establishes metastatic / secondary malignant origin.

    A primary meningeal/dural malignancy (or unspecified malignancy without secondary spread)
    is NOT sufficient for automatic S.
    """
    if not text:
        return False

    # Primary meningeal/dural neoplasm without metastatic mention
    if re.search(r'\bprimary\s+(?:malignant\s+)?(?:dural|meningeal|brain|cranial)\s+(?:tumor|neoplasm|malignancy|lesion)\b', text, re.I):
        if not re.search(r'\b(?:carcinomatosis|metast(?:asis|ases|atic))\b', text, re.I):
            return False

    meta_patterns = [
        r'\b(?:lepto)?meningeal\s+carcinomatosis\b',
        r'\bcarcinomatous\s+meningitis\b',
        r'\b(?:dural|meningeal|leptomeningeal|pial)\s+carcinomatosis\b',
        r'\b(?:dural|meningeal|leptomeningeal|pial)\s+metast(?:asis|ases|atic)\b',
        r'\bmetast(?:atic|ases|asis)\s+(?:involving|of)\s+(?:the\s+)?(?:dura|meninges|leptomeninges|pia)\b',
        r'\b(?:bone|calvarial|skull|vertebral|spine|spinal|clivus|mandibular|extracranial|systemic|diffuse)\s+metast(?:ases|asis|atic)\b',
        r'\bmetast(?:ases|asis)\s+(?:involving|present\s+involving)\s+(?:the\s+)?(?:clivus|cranium|calvarium|vertebrae|bone|spine)\b',
        r'\b(?:known|history\s+of|widespread|multiple|diffuse)\s+metast(?:atic\s+disease|ases|asis)\b',
        r'\bsecondary\s+(?:malignant|neoplastic|tumor)\s+deposits?\b',
        r'\b(?:brain\s+)?metast(?:asis|ases|atic)\b',
    ]
    for pat in meta_patterns:
        for m in re.finditer(pat, text, re.I):
            pre = text[max(0, m.start() - 30):m.start()]
            if not re.search(r'\b(?:no|without|denies|negative\s+for)\s+(?:evidence\s+of\s+)?$', pre, re.I):
                return True
    return False


def extract_evidence(text: str, entry: dict, target_pathology: str, source_mode: str = "full_report") -> list[EvidenceUnit]:
    """
    Extract all matching evidence units from text for a given pathology.
    
    Args:
        text: The source report text.
        entry: The configuration entry for the pathology.
        target_pathology: The target pathology name.
        source_mode: "findings" or "full_report".
        
    Returns:
        A list of EvidenceUnit instances representing extracted matches.
    """
    if not text:
        return []
        
    terms = terms_for_entry(entry)
    matches = find_all_matches(text, terms)
    
    evidence_units = []
    matched_spans = []
    for start, end, matched_text, vocabulary_term in matches:
        # S1: Exclusion preposition scope gating local to Ventriculomegaly
        if target_pathology == "Ventriculomegaly":
            before_match = text[:start]
            if re.search(r'\b(?:except\s+for|excluding|with\s+the\s+exception\s+of|except)\s+(?:the\s+)?$', before_match, re.I):
                continue
        section = section_for_offsets(text, start, end, source_mode=source_mode)
        
        # Invariant check
        if text[start:end] != matched_text:
            raise ValueError(f"Invariant violated: text[{start}:{end}] != '{matched_text}'")
            
        unit = EvidenceUnit(
            text=matched_text,
            start=start,
            end=end,
            section=section,
            matched_term=vocabulary_term,
            target_pathology=target_pathology
        )
        evidence_units.append(unit)
        matched_spans.append((start, end))

    # Task 9: Codebook-backed compositional retrieval
    comp_patterns = entry.get('machine_rules', {}).get('compositional_patterns', [])
    for comp in comp_patterns:
        pat_str = comp.get('pattern', '')
        if not pat_str:
            continue

        pattern = re.compile(pat_str, re.I)
        for m in pattern.finditer(text):
            if "target" in pattern.groupindex:
                start, end = m.span("target")
            else:
                start, end = m.span()
            matched_text = text[start:end]
            # Avoid duplicate if already covered by an exact match
            if any(s <= start and end <= e for s, e in matched_spans):
                continue
            # S1: Exclusion preposition scope gating local to Ventriculomegaly:
            # If the matched target phrase is introduced by an exclusion preposition,
            # the target is exempted from the finding and must not match as an affirmative finding.
            if target_pathology == "Ventriculomegaly":
                before_comp_match = text[:start]
                if re.search(r'\b(?:except\s+for|excluding|with\s+the\s+exception\s+of|except)\s+(?:the\s+)?$', before_comp_match, re.I):
                    continue

            # Clinician Policy Round 1 (Item 3): Generic residual/recurrent tumor phrasing
            # supports a target only if local sentence context explicitly links 'tumor' to that diagnosis.
            pattern_id = comp.get('pattern_id', '')
            if pattern_id in ("COMP_GLIOMA_LINKED_RESIDUAL_TUMOR", "COMP_MENINGIOMA_LINKED_RESIDUAL_TUMOR"):
                from mrhex.engine.segmentation.sentences import sentence_for_offset
                sent_text, _, _ = sentence_for_offset(text, start)
                if pattern_id == "COMP_GLIOMA_LINKED_RESIDUAL_TUMOR":
                    if not re.search(r'\b(?:glioma|glioblastoma|astrocytoma|oligodendroglioma|ependymoma|GBM)\b', sent_text, re.I):
                        continue
                elif pattern_id == "COMP_MENINGIOMA_LINKED_RESIDUAL_TUMOR":
                    if not re.search(r'\bmeningioma\b', sent_text, re.I):
                        continue

            # Clinician Policy Round 3 (Metastatic malignant neoplasm to brain):
            # Direct cortical/parenchymal invasion supports target ONLY if report establishes
            # that the meningeal/dural disease is metastatic (secondary spread).
            # Primary or unspecified malignant invasion alone is insufficient for automatic S.
            if pattern_id == "COMP_METASTASIS_INVASIVE_CORTICAL_PARENCHYMAL":
                if not is_metastatic_origin_established(text):
                    continue

            section = section_for_offsets(text, start, end, source_mode=source_mode)
            unit = EvidenceUnit(
                text=matched_text,
                start=start,
                end=end,
                section=section,
                matched_term=comp.get('pattern_id', target_pathology),
                target_pathology=target_pathology
            )
            evidence_units.append(unit)
            matched_spans.append((start, end))
        
    return evidence_units
