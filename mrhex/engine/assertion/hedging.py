"""Hedging and uncertainty assertion module for deterministic v2."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Optional
import yaml

from mrhex.engine.types import CertaintyLevel, ReasonCode

UNCERTAINTY_CUES = re.compile(
    r'\b(possible|possibly|probable|probably|likely|may|might|could|cannot exclude|suspected|suspicious for|suggestive(?:\s+primarily)?\s+of|suggests?|suggesting|questionable|favored|favoring|in favor of|evaluated in favor of|thought to be|presumed|primarily|(?:raise(?:s|d)?|raising)\s+suspicion\s+(?:for|of)|suspicion\s+(?:for|of))\b', 
    re.I
)

COMPATIBLE_WITH_CUES = re.compile(r'\b(?:compatible with|consistent with)\b', re.I)

POST_TARGET_CUES = re.compile(
    r'\b(cannot be excluded'
    r'|(?:is|are|was|were)\s+(?:considered\s+)?(?:possible|suspicious|questionable|likely|suspected|favored|suggestive)'
    r'|(?:is|are|was|were)\s+(?:possibly|probably|potentially|likely)\s+(?:present|noted|seen|observed)'
    r'|(?:may|might|could)\s+(?:be\s+(?:noted|seen|present|observed|identified|detected|appreciated|considered)|represent)\b'
    r')\b',
    re.I
)

DIFF_PHRASES = re.compile(
    r'\b(differential\s+(?:diagnosis\s+)?(?:includes?|of)|in\s+the\s+differential)\b',
    re.I,
)
VERSUS_PATTERN = re.compile(r'\b(?:versus|vs\.?)\b', re.I)
_COORDINATION_MODIFIERS = {
    "acute", "chronic", "subacute", "old", "new", "residual", "recurrent",
    "left", "right", "bilateral", "mild", "moderate", "severe", "small",
    "large", "sized", "size",
}

_CACHED_GLOBAL_OVERRIDES: dict | None = None


def get_default_global_overrides() -> dict:
    """Load and cache global_policy_overrides from configs/final_deterministic_rules_v2.yaml."""
    global _CACHED_GLOBAL_OVERRIDES
    if _CACHED_GLOBAL_OVERRIDES is not None:
        return _CACHED_GLOBAL_OVERRIDES

    yaml_path = Path(__file__).resolve().parents[3] / "configs" / "final_deterministic_rules_v2.yaml"
    if yaml_path.exists():
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                _CACHED_GLOBAL_OVERRIDES = data.get("global_policy_overrides", {})
                return _CACHED_GLOBAL_OVERRIDES
        except Exception:
            pass

    _CACHED_GLOBAL_OVERRIDES = {}
    return _CACHED_GLOBAL_OVERRIDES


def _contains_other_target_term(text: str, target_terms: tuple[str, ...]) -> bool:
    """Whether the opposing operand names the same configured target lineage.

    This is deliberately vocabulary-driven rather than pathology-name-driven: only
    already configured literal target terms may preserve a bare ``or`` as a
    same-lineage alternative (for example, two approved surface forms).
    """
    for term in target_terms:
        cleaned = " ".join(str(term).split())
        if not cleaned or cleaned.startswith("COMP_"):
            continue
        if re.search(rf"(?<!\w){re.escape(cleaned)}(?!\w)", text, re.I):
            return True
    return False


def _is_target_in_disjunction(
    clause: str,
    target_start: int,
    target_end: int,
    target_terms: tuple[str, ...] = (),
) -> bool:
    """Check whether the target is an operand of an unresolved alternative.

    Bare ``or`` is a differential when it directly joins the matched target to
    a non-target operand.  Existing configured target terms on the other side
    establish same-lineage coordination and are intentionally preserved.
    """
    before_target = clause[:target_start].strip()
    after_target = clause[target_end:].strip()

    # e.g., '<target> vs ...'
    if re.match(r'^(?:versus|vs\.?)\b', after_target, re.I):
        return True

    # e.g., '... vs <target>'
    if re.search(r'\b(?:versus|vs\.?)\s*$', before_target, re.I):
        return True

    # Check for explicit differential phrase in clause
    if DIFF_PHRASES.search(clause) or VERSUS_PATTERN.search(clause):
        return True

    # Direct bare or hedged disjunction. A target-term vocabulary check prevents
    # same-lineage alternatives such as approved synonym pairs from being routed.
    or_before = re.search(r'\b(?:or)\s*$', before_target, re.I)
    if not or_before:
        # A target can be preceded by coordinated modifiers: 'acute or chronic
        # subdural hematoma' must remain parent-target support, whereas
        # 'hygroma or chronic subdural hematoma' is a target/non-target choice.
        matches = list(re.finditer(r'\bor\b', before_target, re.I))
        if matches:
            candidate = matches[-1]
            trailing = re.findall(r"\b[\w-]+\b", before_target[candidate.end():].lower())
            leading_words = re.findall(r"\b[\w-]+\b", before_target[:candidate.start()].lower())
            if trailing and all(word in _COORDINATION_MODIFIERS for word in trailing):
                if leading_words and leading_words[-1] in _COORDINATION_MODIFIERS:
                    return False
                if not _contains_other_target_term(before_target[:candidate.start()], target_terms):
                    return True
    if or_before:
        opposing = before_target[:or_before.start()]
        if not _contains_other_target_term(opposing, target_terms):
            return True

    or_after = re.match(r'^\s*\bor\b', after_target, re.I)
    if or_after:
        opposing = after_target[or_after.end():]
        if not _contains_other_target_term(opposing, target_terms):
            return True

    return False


def analyze_hedging(
    clause: str,
    target_start: int,
    target_end: int,
    target_term: str = "",
    global_overrides: dict | None = None,
    target_pathology: str = "",
    target_terms: tuple[str, ...] = (),
) -> tuple[CertaintyLevel, list[ReasonCode]]:

    """Analyze uncertainty and hedging within a clause consuming global_policy_overrides.
    
    R04 Policy Conformance:
    - Runtime consumes machine-readable global_policy_overrides from v2 config:
      * compatible_with_single: S (DEFINITE)
      * compatible_with_alternative: UC (HEDGED)
      * consistent_with_single: S (DEFINITE)
      * likely, probable, favored, possible, suggestive_of, suspicious_for,
        may_represent, could_represent, cannot_exclude: UC (HEDGED)
    - Target-local differential detection:
      Alternatives must refer to competing TARGET diagnoses/entities:
      'meningioma versus schwannoma', 'compatible with metastasis or glioma'
      Do NOT treat modifier coordination ('without edema or mass effect') as a differential.
    - Simple bounded hedge maps to UC (ASSERT_HEDGED).
    - Competing differential maps to DIFFERENTIAL / DIFFERENTIAL_OR_ALTERNATIVE.
    - Disjunctive uncertainty maps to HEDGED / DIFFERENTIAL_OR_ALTERNATIVE.
    
    Args:
        clause: The text of the clause containing the target.
        target_start: Start index of the target term in the clause.
        target_end: End index of the target term in the clause.
        target_term: The target term itself.
        global_overrides: Optional dictionary of global policy overrides.
        
    Returns:
        tuple[CertaintyLevel, list[ReasonCode]]: The certainty level and reason codes.
    """
    if not global_overrides:
        global_overrides = get_default_global_overrides()

    before_target = clause[:target_start]
    after_target = clause[target_end:]

    # Label-scoped hedging adjustment for Cerebral atrophy and Gliosis:
    # "primarily" functions as distribution/predominance (Type 1) or causal predominance (Type 2)
    # rather than diagnostic uncertainty when modifying distribution, background, or causal attribution.
    if target_pathology in ("Cerebral atrophy", "Gliosis"):
        def _sub_causal_dist_primarily(m: re.Match) -> str:
            span = m.group(0)
            return re.sub(r'\bprimarily\b', ' ' * len('primarily'), span, flags=re.I)

        clause = re.sub(
            r'\bprimarily\s+(?:(?:as\s+)?(?:secondary\s+to|due\s+to)|on|in|involving|affecting)\b',
            _sub_causal_dist_primarily,
            clause,
            flags=re.I,
        )
        before_target = clause[:target_start]
        after_target = clause[target_end:]

    # Label-scoped uncertainty check for Silent micro-hemorrhage of brain
    if target_pathology == "Silent micro-hemorrhage of brain" and re.search(r"\bpotentially\b", before_target, re.I):
        return CertaintyLevel.HEDGED, [ReasonCode.ASSERT_HEDGED]

    # Label-scoped uncertainty check for Demyelinating disease of central nervous system
    if target_pathology == "Demyelinating disease of central nervous system":
        if re.search(
            r'\b(?:correlation\s+with\s+(?:the\s+)?clinical\s+(?:picture|findings)\s+is\s+recommended|'
            r'recommended\s+for\s+clinical\s+evaluation|'
            r'clinical\s+(?:and\s+laboratory\s+)?correlation\s+is\s+recommended|'
            r'clinical\s+lab\s+and\s+correlation\s+are\s+recommended|'
            r'clinical\s+correlation\s+is\s+recommended)\b',
            before_target + " " + after_target,
            re.I
        ):
            return CertaintyLevel.HEDGED, [ReasonCode.ASSERT_HEDGED]

        if re.search(r'\b(?:atypical|presumptive)\b', before_target, re.I):
            return CertaintyLevel.HEDGED, [ReasonCode.ASSERT_HEDGED]

        if re.search(r'\b(?:vasculitis\?|ischemic\?|infection\?)\b', before_target, re.I):
            return CertaintyLevel.HEDGED, [ReasonCode.ASSERT_HEDGED]

    # Check for target-local differential or competing entity
    if _is_target_in_disjunction(clause, target_start, target_end, target_terms):
        if UNCERTAINTY_CUES.search(before_target) or COMPATIBLE_WITH_CUES.search(before_target):
            # Disjunctive uncertainty: 'compatible with metastasis or glioma'
            override_state = global_overrides.get("compatible_with_alternative", {}).get("state", "UC")
            if override_state == "UC":
                return CertaintyLevel.HEDGED, [ReasonCode.DIFFERENTIAL_OR_ALTERNATIVE]
            elif override_state == "S":
                return CertaintyLevel.DEFINITE, []
            return CertaintyLevel.HEDGED, [ReasonCode.DIFFERENTIAL_OR_ALTERNATIVE]
        # Direct differential: 'meningioma versus schwannoma'
        return CertaintyLevel.DIFFERENTIAL, [ReasonCode.DIFFERENTIAL_OR_ALTERNATIVE]

    # Check for sole affirmative compatible with / consistent with
    cw_match = COMPATIBLE_WITH_CUES.search(before_target)
    if cw_match:
        cw_text = cw_match.group().lower()
        if "compatible" in cw_text:
            override_state = global_overrides.get("compatible_with_single", {}).get("state", "S")
        else:
            override_state = global_overrides.get("consistent_with_single", {}).get("state", "S")

        # Check for additional hedging:
        # 1. Before compatible/consistent with (e.g. 'possibly compatible with', 'probably compatible with', 'primarily compatible with')
        # 2. Intervening between compatible/consistent with and target (e.g. 'compatible with probable mastoiditis')
        # 3. Post-target hedging attached to target (e.g. 'compatible with mastoiditis, cannot be excluded')
        has_question_mark = (
            bool(re.match(r'^\s*(?:[\w-]+\s+){0,3}[\w-]*\s*\?', after_target))
            or bool(re.search(r'\([^)]*$', before_target) and re.search(r'^[^(]*\?[^)]*\)', after_target))
            or bool(re.search(r'\?\s*$', before_target))
        )
        pre_text = before_target[:cw_match.start()].rstrip()
        pre_hedge = bool(UNCERTAINTY_CUES.search(pre_text))
        intervening_hedge = bool(UNCERTAINTY_CUES.search(before_target[cw_match.end():]))
        post_hedge = bool(POST_TARGET_CUES.search(after_target)) or has_question_mark
        if not post_hedge:
            post_match = UNCERTAINTY_CUES.search(after_target)
            if post_match:
                between_target_and_post = after_target[:post_match.start()]
                if len(re.findall(r"\b\w+\b", between_target_and_post)) <= 3:
                    post_hedge = True

        matched_clause_span = clause[target_start:target_end]
        has_compound_alternative = bool(
            re.search(r'[-/]\s*(?:infiltration|tumor|glioma|metastasis|infection|ischemia)\b', target_term, re.I)
            or re.search(r'[-/]\s*(?:infiltration|tumor|glioma|metastasis|infection|ischemia)\b', matched_clause_span, re.I)
            or re.match(r'^\s*[-/]\s*(?:infiltration|tumor|glioma|metastasis|infection|ischemia)\b', after_target, re.I)
        )
        if pre_hedge or intervening_hedge or post_hedge or has_compound_alternative:
            # "compatible with" PLUS additional hedging or alternative -> UC
            code = ReasonCode.DIFFERENTIAL_OR_ALTERNATIVE if has_compound_alternative else ReasonCode.ASSERT_HEDGED
            return CertaintyLevel.HEDGED, [code]

        if override_state == "S":
            return CertaintyLevel.DEFINITE, []
        elif override_state == "UC":
            return CertaintyLevel.HEDGED, [ReasonCode.ASSERT_HEDGED]

    # Check for atypical/differential framing: 'atypical for <target>'
    atypical_matches = list(re.finditer(r'\batypical\s+for\b', before_target, re.I))
    if atypical_matches:
        last_atypical = atypical_matches[-1]
        between = before_target[last_atypical.end():]
        if len(re.findall(r"\b\w+\b", between)) <= 3:
            return CertaintyLevel.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]

    is_hedged = False

    # Check if the matched span itself contains an uncertainty cue (e.g. compositional patterns)
    matched_clause_span = clause[target_start:target_end]
    span_cue = UNCERTAINTY_CUES.search(matched_clause_span)
    if span_cue:
        is_hedged = True

    # Pre-target hedging directly attached to target
    cues = list(UNCERTAINTY_CUES.finditer(before_target))
    if cues:
        cue = cues[-1]
        between = before_target[cue.end():]
        # Ambiguity check (complex/multi-clause: >5 words or punctuation between cue and target)
        if bool(re.search(r"[,;]", between)) or len(re.findall(r"\b\w+\b", between)) > 5:
            return CertaintyLevel.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]
        
        # Check override state for the cue
        cue_word = cue.group().lower()
        override_key = None
        if "likely" in cue_word:
            override_key = "likely"
        elif "probable" in cue_word:
            override_key = "probable"
        elif any(w in cue_word for w in ("favored", "favoring", "in favor")):
            override_key = "favored"
        elif "possible" in cue_word or "possibly" in cue_word:
            override_key = "possible"
        elif "suggest" in cue_word:
            override_key = "suggestive_of"
        elif "suspicious" in cue_word:
            override_key = "suspicious_for"
        elif "may" in cue_word:
            override_key = "may_represent"
        elif "could" in cue_word:
            override_key = "could_represent"
        elif "cannot exclude" in cue_word:
            override_key = "cannot_exclude"

        if override_key and override_key in global_overrides:
            state = global_overrides[override_key].get("state", "UC")
            if state == "UC":
                is_hedged = True
            elif state == "S":
                is_hedged = False
        else:
            is_hedged = True

    # Post-target hedging attached to target or parenthetical question mark
    has_question_mark = (
        bool(re.match(r'^\s*(?:[\w-]+\s+){0,3}[\w-]*\s*\?', after_target))
        or bool(re.search(r'\([^)]*$', before_target) and re.search(r'^[^(]*\?[^)]*\)', after_target))
        or bool(re.search(r'\?\s*$', before_target))
    )
    if POST_TARGET_CUES.search(after_target) or has_question_mark:
        is_hedged = True

    if is_hedged:
        reasons = [ReasonCode.ASSERT_HEDGED]
        if has_question_mark and target_pathology == "Intracranial meningioma":
            reasons.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)
        return CertaintyLevel.HEDGED, reasons

    return CertaintyLevel.DEFINITE, []
