"""Negation assertion module for deterministic v2."""
import re

from mrhex.engine.types import AssertionPolarity, ReasonCode
from mrhex.engine.assertion.modifiers import is_modifier_between, TEMPORAL_MODIFIER_QUALIFIERS

NEGATION_CUES = re.compile(r'\b(no|not|without|negative for|absent|absence of|free of)\b', re.I)

def analyze_negation(
    clause: str,
    target_start: int,
    target_end: int,
    target_term: str,
    chronicity_constraint: str = "",
) -> tuple[AssertionPolarity, list[ReasonCode]]:
    """Analyze negation within a clause to determine polarity and assign reason codes.
    
    R03 Policy Conformance:
    - Distinguishes:
      A. Negated target with temporal/severity qualifier:
         'no acute hemorrhage', 'no active demyelination', 'no significant stenosis'
         The target itself is inside negation scope with a qualifier.
         MUST NOT emit S or NEGATED_MODIFIER.
         If chronicity aligns with target definition, produces C; otherwise AMBIGUOUS/routes.
      B. Negated modifier of an affirmed target:
         'meningioma without edema', 'tumor without enhancement', 'no enhancement of the meningioma'
         Target is affirmed, modifier is negated.
         Produces NEGATED_MODIFIER (affirmed target).
    
    Args:
        clause: The text of the clause containing the target.
        target_start: Start index of the target term in the clause.
        target_end: End index of the target term in the clause.
        target_term: The target term itself.
        chronicity_constraint: Optional target-specific chronicity requirement.
        
    Returns:
        tuple[AssertionPolarity, list[ReasonCode]]: The polarity and reason codes.
    """
    # Check for POST-TARGET negation (e.g. "meningioma is ruled out", "bleed was absent")
    after_target = clause[target_end:]
    if re.search(r'\b(was absent|is ruled out|are ruled out|is excluded|are excluded|absent)\b', after_target, re.I):
        return AssertionPolarity.NEGATED, [ReasonCode.ASSERT_TARGET_NEGATED]

    cues = list(NEGATION_CUES.finditer(clause))
    if not cues:
        return AssertionPolarity.AFFIRMED, []

    preceding = [cue for cue in cues if cue.end() <= target_start]
    if preceding:
        cue = preceding[-1]
        between = clause[cue.end():target_start]

        # Exception preposition between cue and target carves out target from negation scope:
        # e.g., 'no focal parenchymal metastases apart from cerebral cortical invasion' -> target is affirmed
        if re.search(r'\b(?:apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than)\b\s*$', between, re.I):
            return AssertionPolarity.AFFIRMED, []

        # Case A: Temporal/severity qualifier preceding target entity:
        # e.g., 'no acute hemorrhage', 'no active demyelination', 'no significant stenosis'
        # The target itself is qualified and negated. MUST NOT become target affirmation!
        has_qualifier = any(
            re.search(rf'\b{re.escape(q)}\b', between, re.I)
            for q in TEMPORAL_MODIFIER_QUALIFIERS
        )
        if has_qualifier:
            # If target definition specifically requires this qualifier (e.g. 'acute infarct'):
            if chronicity_constraint.lower() == "acute" or "acute" in target_term.lower():
                return AssertionPolarity.NEGATED, [ReasonCode.ASSERT_TARGET_NEGATED]
            # Broad target where qualified negation does not safely imply general C:
            # Must route to LLM due to unestablished/ambiguous chronicity, NEVER emit S!
            return AssertionPolarity.AMBIGUOUS, [ReasonCode.CHRONICITY_UNESTABLISHED]

        # Case B: Negated modifier between cue and target:
        # e.g., 'no enhancement in the meningioma'
        # Modifier is negated, parent entity is affirmed.
        is_mod, mod_term = is_modifier_between(clause, cue.end(), target_start)
        if is_mod and mod_term.lower() not in target_term.lower():
            return AssertionPolarity.NEGATED_MODIFIER, [ReasonCode.NEGATED_MODIFIER_NOT_TARGET]

        # Ambiguous scope check (>4 words or punctuation/conjunctions between cue and target)
        # Allow coordinated modifier pairs modifying target: 'residual or recurrent', 'acute or chronic'
        is_coord_modifier = bool(re.search(r"^\s*(?:residual|recurrent|acute|chronic|subacute|new|old)\s+(?:or|and)\s*$", between, re.I))
        if not is_coord_modifier and (bool(re.search(r"[,;]|\b(?:and|or|with)\b", between, re.I)) or len(re.findall(r"\b\w+\b", between)) > 4):
            return AssertionPolarity.AMBIGUOUS, [ReasonCode.MALFORMED_OR_COMPLEX_SCOPE]

        # Direct unconditioned negation of target: 'no hemorrhage', 'no meningioma'
        return AssertionPolarity.NEGATED, [ReasonCode.ASSERT_TARGET_NEGATED]

    return AssertionPolarity.AFFIRMED, []

