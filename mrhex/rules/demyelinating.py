"""Deterministic Standalone Fallback Rules for Demyelinating Disease of Central Nervous System.

Implements accepted standalone rules with anatomy-aware evidence reconciliation:
  - DM-ST-1: Direct lexical variants (demyelination, MS plaques, multiple sclerosis plaques)
  - DM-ST-2: Characteristic morphology with explicit demyelinating attribution (perpendicular to ventricles/callosum + MS, Dawson fingers)
  - DM-ST-3: Inactive/chronic plaques & MS-context plaque findings (inactive plaques, plaques in patient diagnosed with MS)
  - DM-ST-4: Uncertain differential language (suspicious for demyelinating disease, MS?, differential includes MS) -> UC

Anatomy-Aware Evidence Reconciliation:
  - Demyelinating disease of the CNS is a CNS-wide target encompassing supratentorial brain,
    infratentorial brain/brainstem/cerebellum, and spinal cord compartments.
  - Compartment-scoped negations (e.g. "no demyelinating plaque in brain" or "no intracortical plaque")
    do NOT negate positive demyelinating findings in other compartments (e.g. cervical or thoracic spinal cord).
  - Descriptions of non-enhancement or stability (e.g. "showing no contrast enhancement", "no significant change")
    describe plaque properties (inactive/stable status), NOT plaque absence, and do not negate plaques.
  - Definite positive evidence in any valid CNS compartment yields S (unless higher-priority policy applies).
  - C is produced only when negative evidence covers the target globally or all investigated compartments without conflicting positive evidence.

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2.
"""
from __future__ import annotations

import re
from typing import Any

# Assertion helpers
NEGATION_CUE = re.compile(
    r"\b(?:no\b|without|denies|negative\s+for|ruled\s+out|no\s+evidence\s+of|is\s+not\s+observed|not\s+detected)\b",
    re.I,
)
HEDGING_CUE = re.compile(
    r"\b(?:questionable|equivocal|possible|possibly|cannot\s+exclude|could\s+represent|"
    r"may\s+represent|in\s+favor\s+of|favoring|thought\s+to\s+be|suspicious\s+for|raises\s+suspicion)\b|\?",
    re.I,
)

# Direct plaque negation prefix (e.g., "no demyelinating plaque", "without MS plaques")
PLAQUE_NEG_PREFIX = re.compile(
    r"\b(?:no\b|without|negative\s+for|ruled\s+out|no\s+evidence\s+of|denies)\b",
    re.I,
)

# Plaque negation suffix (e.g., "plaque was not detected", "are not observed")
PLAQUE_NEG_SUFFIX = re.compile(
    r"\b(?:is\s+not\s+(?:observed|detected|seen|identified)|"
    r"are\s+not\s+(?:observed|detected|seen|identified)|"
    r"was\s+not\s+(?:observed|detected|seen|identified)|"
    r"were\s+not\s+(?:observed|detected|seen|identified)|"
    r"not\s+(?:observed|detected|seen|identified)|"
    r"ruled\s+out)\b",
    re.I,
)

# Enhancement / stability qualifiers that describe plaque properties, NOT absence
ENHANCEMENT_OR_STABILITY_NEGATION = re.compile(
    r"\b(?:showing\s+no\s+(?:significant\s+)?(?:contrast\s+)?(?:enhancement|uptake|change)|"
    r"no\s+(?:significant\s+)?(?:contrast\s+)?(?:enhancement|uptake|change)|"
    r"without\s+(?:significant\s+)?(?:contrast\s+)?(?:enhancement|uptake|change)|"
    r"not\s+showing\s+(?:contrast\s+)?(?:enhancement|uptake)|"
    r"do\s+not\s+show\s+(?:contrast\s+)?(?:enhancement|uptake)|"
    r"no\s+diffusion\s+restriction)\b",
    re.I,
)

# Compartment lexicons
SPINE_TERMS = re.compile(
    r"\b(?:"
    r"spinal|cord|cervical|thoracic|dorsal|craniocervical|bulbocervical|"
    r"lumbar|medulla\s+spinalis|myelon|conus|cauda|"
    r"C[1-8]|T[1-9]|T1[0-2]|L[1-5]"
    r")\b",
    re.I,
)

BRAIN_TERMS = re.compile(
    r"\b(?:"
    r"brain|cranial|cerebral|cerebrum|hemispher\w*|intracranial|"
    r"supratentorial|supra[\-\s]?infratentorial|intracortical|cortex|"
    r"periventricular|callos\w*|centrum\s+semiovale|corona\s+radiata|"
    r"frontal|parietal|temporal|occipital|subcortical|ventricl\w*|"
    r"infratentorial|posterior\s+fossa|brainstem|pons|pontine|"
    r"medulla\s+oblongata|midbrain|cerebell\w*|peduncle|pontomedullary"
    r")\b",
    re.I,
)

GLOBAL_NEGATION_PAT = re.compile(
    r"\b(?:"
    r"no\s+evidence\s+of\s+(?:demyelinat\w*|multiple\s+sclerosis|MS)|"
    r"no\s+(?:demyelinat\w*|MS|multiple\s+sclerosis)\s+plaques?\s+(?:in\s+(?:the\s+)?(?:brain|head|cranial|cerebral)\s+(?:and|or)\s+(?:spinal\s+)?cord|in\s+CNS)|"
    r"no\s+CNS\s+demyelinating\s+plaques?|"
    r"no\s+evidence\s+of\s+multiple\s+sclerosis[\-\s]related\s+plaques?|"
    r"negative\s+for\s+demyelinating\s+disease"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# DM-ST-1: Direct lexical variants
# ------------------------------------------------------------------------------
DM_ST1_PAT = re.compile(
    r"\b(?:"
    r"demyelinat\w*|"
    r"multiple\s+sclerosis\s+plaques?|"
    r"MS\s+plaques?"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# DM-ST-2: Characteristic morphology with explicit demyelinating attribution
# ------------------------------------------------------------------------------
DM_ST2_PAT = re.compile(
    r"\b(?:"
    r"(?:perpendicular\s+to\s+(?:the\s+)?(?:lateral\s+)?ventricles|orientation\s+perpendicular\s+to\s+(?:the\s+)?corpus\s+callosum)[^\.\n]*?(?:significant\s+for\s+MS|MS\s+diagnosis|demyelinat\w*)|"
    r"(?:significant\s+for\s+MS|consistent\s+with\s+MS|compatible\s+with\s+MS)|"
    r"Dawson(?:'s)?\s+fingers?"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# DM-ST-3: Inactive/chronic plaques & MS-context plaque findings
# ------------------------------------------------------------------------------
DM_ST3_PAT = re.compile(
    r"\b(?:"
    r"(?:inactive|stable|non[\-\s]?enhancing|chronic|predominantly\s+inactive)\s+plaques?|"
    r"plaques?\s+(?:are\s+)?(?:inactive|stable|non[\-\s]?enhancing)|"
    r"plaques?\s+in\s+a\s+patient\s+with\s+(?:a\s+)?(?:diagnosis|preliminary\s+diagnosis|follow[\-\s]?up)\s+of\s+(?:multiple\s+sclerosis|MS)|"
    r"new\s+plaque\s+(?:formation\s+)?in\s+a\s+patient\s+diagnosed\s+with\s+(?:multiple\s+sclerosis|MS)|"
    r"multiple\s+plaques\s+showing\s+confluence|"
    r"plaque\s+located\s+in\s+(?:the\s+)?(?:right|left|cervical|thoracic|dorsal|spinal)?\s*cord|"
    r"in\s+the\s+anterior\s+part\s+of\s+the\s+cord[^\.\n]*?non[\-\s]?enhancing\s+plaque"
    r")\b",
    re.I,
)

MS_PATIENT_CTX = re.compile(
    r"\b(?:"
    r"in\s+a\s+patient\s+(?:with\s+(?:a\s+)?|diagnosed\s+with\s+|followed\s+with\s+(?:an?\s+)?)(?:diagnosis\s+of\s+)?(?:MS|multiple\s+sclerosis)|"
    r"MS\s+(?:under\s+)?follow[\-\s]?up|follow[\-\s]?up\s+for\s+MS"
    r")\b",
    re.I,
)

MS_PLAQUE_SUB = re.compile(
    r"\b(?:"
    r"(?:active|inactive|stable|non[\-\s]?enhancing|subacute|new|confluent|hyperintense|millimetric)\s+(?:new\s+)?plaques?|"
    r"plaques?\s+(?:formation|appearance|are\s+noted|were\s+observed|in\s+the|described)|"
    r"multiple\s+plaques|"
    r"lesions\s+persisting\s+in\s+(?:the\s+)?corpus\s+callosum"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# DM-ST-4: Uncertain differential language
# ------------------------------------------------------------------------------
DM_ST4_PAT = re.compile(
    r"\b(?:"
    r"cannot\s+exclude\s+demyelinat\w*|demyelinat\w*\s+should\s+be\s+considered|"
    r"suspicious\s+for\s+demyelinat\w*|raises\s+suspicion\s+for\s+demyelinat\w*|"
    r"demyelinat\w*\s+process\?|differential\s+includes\s+(?:demyelinat\w*|MS)|"
    r"raises\s+suspicion\s+for\s+demyelinating\s+disease\s*\(MS\??\)"
    r")\b",
    re.I,
)


def determine_compartment(clause: str) -> str:
    """Classify anatomical compartment of a clause/sentence."""
    has_spine = bool(SPINE_TERMS.search(clause))
    has_brain = bool(BRAIN_TERMS.search(clause))
    if has_spine and not has_brain:
        return "SPINE"
    if has_brain and not has_spine:
        return "BRAIN"
    if has_spine and has_brain:
        return "MULTI"
    return "UNSPECIFIED"


def is_true_plaque_negation(clause: str, match_start: int, match_end: int) -> bool:
    """Check if the plaque finding itself is truly negated, ignoring enhancement/stability descriptions."""
    prefix = clause[max(0, match_start - 40):match_start]
    suffix = clause[match_end:min(len(clause), match_end + 50)]

    # Check prefix negation
    if PLAQUE_NEG_PREFIX.search(prefix):
        return True

    # Check suffix negation: ensure it's not merely describing non-enhancement or lack of change
    m_suf = PLAQUE_NEG_SUFFIX.search(suffix)
    if m_suf:
        return True

    # If suffix has "no" or "without", verify it is not enhancement/stability
    if re.search(r"\b(?:no|without)\b", suffix, re.I):
        if ENHANCEMENT_OR_STABILITY_NEGATION.search(suffix):
            # This is describing non-enhancement / stability, NOT plaque absence
            return False
        # If it says "no other plaque", that's exclusionary, not negating this plaque
        if re.search(r"\bno\s+(?:other|further|additional|new)\b", suffix, re.I):
            return False

    return False


def evaluate_demyelinating_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules with anatomy-aware evidence reconciliation."""
    clean_text = text.strip()
    if not clean_text:
        return None

    # Step 1: Check for explicit global contradiction across the entire CNS
    for line in clean_text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        m_glob = GLOBAL_NEGATION_PAT.search(ls)
        if m_glob:
            # Check if there is NO positive plaque anywhere in the report
            has_positive = False
            for l2 in clean_text.splitlines():
                l2s = l2.strip()
                if not l2s or l2s == ls:
                    continue
                if DM_ST1_PAT.search(l2s) or DM_ST2_PAT.search(l2s) or DM_ST3_PAT.search(l2s):
                    has_positive = True
                    break
            if not has_positive:
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_DM_GLOBAL_CONTRADICTION_C",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "GLOBAL_CNS_CONTRADICTION"],
                    "evidence_spans": [{"text": m_glob.group(0), "matched_term": m_glob.group(0), "clause_text": ls}],
                }

    # Step 2: Collect positive and negative evidence units by anatomical compartment
    positive_units: list[dict[str, Any]] = []
    negative_units: list[dict[str, Any]] = []

    # 1. Rule DM-ST-4: Uncertain differential language (maps to UC)
    for line in clean_text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        m = DM_ST4_PAT.search(ls)
        if m:
            comp = determine_compartment(ls)
            prefix = ls[max(0, m.start() - 40):m.start()]
            if PLAQUE_NEG_PREFIX.search(prefix):
                negative_units.append({
                    "compartment": comp,
                    "state": "C",
                    "rule_id": "FALLBACK_DM_ST4_DIFFERENTIAL_NEGATED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            else:
                positive_units.append({
                    "compartment": comp,
                    "state": "UC",
                    "rule_id": "FALLBACK_DM_ST4_DIFFERENTIAL_HEDGED",
                    "clause": ls,
                    "matched": m.group(0),
                })

    # 2. Rule DM-ST-2: Characteristic morphology with explicit demyelinating attribution
    for line in clean_text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        m = DM_ST2_PAT.search(ls)
        if m:
            comp = determine_compartment(ls)
            if is_true_plaque_negation(ls, m.start(), m.end()):
                negative_units.append({
                    "compartment": comp,
                    "state": "C",
                    "rule_id": "FALLBACK_DM_ST2_MORPHOLOGY_NEGATED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            elif HEDGING_CUE.search(ls[max(0, m.start() - 40):m.start()]) or HEDGING_CUE.search(ls[m.end():min(len(ls), m.end() + 40)]):
                positive_units.append({
                    "compartment": comp,
                    "state": "UC",
                    "rule_id": "FALLBACK_DM_ST2_MORPHOLOGY_HEDGED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            else:
                positive_units.append({
                    "compartment": comp,
                    "state": "S",
                    "rule_id": "FALLBACK_DM_ST2_MORPHOLOGY_AFFIRMED",
                    "clause": ls,
                    "matched": m.group(0),
                })

    # 3. Rule DM-ST-3: Inactive/chronic plaques & MS-context plaque findings
    has_ms_ctx = bool(MS_PATIENT_CTX.search(clean_text))
    if has_ms_ctx:
        for line in clean_text.splitlines():
            ls = line.strip()
            if not ls:
                continue
            m = MS_PLAQUE_SUB.search(ls)
            if m:
                comp = determine_compartment(ls)
                if is_true_plaque_negation(ls, m.start(), m.end()):
                    negative_units.append({
                        "compartment": comp,
                        "state": "C",
                        "rule_id": "FALLBACK_DM_ST3_MS_CONTEXT_NEGATED",
                        "clause": ls,
                        "matched": m.group(0),
                    })
                elif HEDGING_CUE.search(ls[max(0, m.start() - 40):m.start()]):
                    positive_units.append({
                        "compartment": comp,
                        "state": "UC",
                        "rule_id": "FALLBACK_DM_ST3_MS_CONTEXT_HEDGED",
                        "clause": ls,
                        "matched": m.group(0),
                    })
                else:
                    positive_units.append({
                        "compartment": comp,
                        "state": "S",
                        "rule_id": "FALLBACK_DM_ST3_MS_CONTEXT_AFFIRMED",
                        "clause": ls,
                        "matched": m.group(0),
                    })

    for line in clean_text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        m = DM_ST3_PAT.search(ls)
        if m:
            comp = determine_compartment(ls)
            if is_true_plaque_negation(ls, m.start(), m.end()):
                negative_units.append({
                    "compartment": comp,
                    "state": "C",
                    "rule_id": "FALLBACK_DM_ST3_CHRONIC_NEGATED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            elif HEDGING_CUE.search(ls[max(0, m.start() - 40):m.start()]) or HEDGING_CUE.search(ls[m.end():min(len(ls), m.end() + 40)]):
                positive_units.append({
                    "compartment": comp,
                    "state": "UC",
                    "rule_id": "FALLBACK_DM_ST3_CHRONIC_HEDGED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            else:
                positive_units.append({
                    "compartment": comp,
                    "state": "S",
                    "rule_id": "FALLBACK_DM_ST3_CHRONIC_AFFIRMED",
                    "clause": ls,
                    "matched": m.group(0),
                })

    # 4. Rule DM-ST-1: Direct lexical variants
    for line in clean_text.splitlines():
        ls = line.strip()
        if not ls:
            continue
        m = DM_ST1_PAT.search(ls)
        if m:
            comp = determine_compartment(ls)
            if is_true_plaque_negation(ls, m.start(), m.end()):
                negative_units.append({
                    "compartment": comp,
                    "state": "C",
                    "rule_id": "FALLBACK_DM_ST1_DIRECT_NEGATED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            elif HEDGING_CUE.search(ls[max(0, m.start() - 40):m.start()]) or HEDGING_CUE.search(ls[m.end():min(len(ls), m.end() + 40)]):
                positive_units.append({
                    "compartment": comp,
                    "state": "UC",
                    "rule_id": "FALLBACK_DM_ST1_DIRECT_HEDGED",
                    "clause": ls,
                    "matched": m.group(0),
                })
            else:
                positive_units.append({
                    "compartment": comp,
                    "state": "S",
                    "rule_id": "FALLBACK_DM_ST1_DIRECT_AFFIRMED",
                    "clause": ls,
                    "matched": m.group(0),
                })

    # Step 3: Multi-compartment Evidence Reconciliation
    if not positive_units and not negative_units:
        return None

    # Definite positive units (state == 'S')
    definite_pos = [u for u in positive_units if u["state"] == "S"]
    uncertain_pos = [u for u in positive_units if u["state"] == "UC"]

    # Invariant: If at least one valid CNS compartment has definite current positive evidence -> output S
    if definite_pos:
        # Production precedence: DM-ST-2 -> DM-ST-3 -> DM-ST-1
        order = {"FALLBACK_DM_ST2": 1, "FALLBACK_DM_ST3": 2, "FALLBACK_DM_ST1": 3}
        best_u = min(definite_pos, key=lambda u: next((v for k, v in order.items() if u["rule_id"].startswith(k)), 99))
        return {
            "standalone_state": "S",
            "fallback_rule_id": best_u["rule_id"],
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "ANATOMY_RECONCILED_AFFIRMED"],
            "evidence_spans": [{"text": best_u["matched"], "matched_term": best_u["matched"], "clause_text": best_u["clause"]}],
        }

    # If no definite positive, but uncertain positive exists -> output UC
    if uncertain_pos:
        order = {"FALLBACK_DM_ST4": 1, "FALLBACK_DM_ST2": 2, "FALLBACK_DM_ST3": 3, "FALLBACK_DM_ST1": 4}
        best_u = min(uncertain_pos, key=lambda u: next((v for k, v in order.items() if u["rule_id"].startswith(k)), 99))
        return {
            "standalone_state": "UC",
            "fallback_rule_id": best_u["rule_id"],
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "ANATOMY_RECONCILED_HEDGED"],
            "evidence_spans": [{"text": best_u["matched"], "matched_term": best_u["matched"], "clause_text": best_u["clause"]}],
        }

    # If only negative units exist -> output C
    if negative_units:
        best_u = negative_units[0]
        return {
            "standalone_state": "C",
            "fallback_rule_id": best_u["rule_id"],
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "ANATOMY_RECONCILED_NEGATED"],
            "evidence_spans": [{"text": best_u["matched"], "matched_term": best_u["matched"], "clause_text": best_u["clause"]}],
        }

    return None
