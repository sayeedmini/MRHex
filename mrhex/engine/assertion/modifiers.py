"""Modifier vocabulary and matching logic for R03."""
import re

MODIFIER_TERMS: set[str] = {
    'enhancement', 'enhancing', 'contrast enhancement',
    'edema', 'surrounding edema', 'perilesional edema', 'vasogenic edema',
    'mass effect', 'midline shift',
    'hydrocephalus', 'obstructive hydrocephalus',
    'hemorrhage', 'hemorrhagic', 'hemorrhagic transformation',
    'restricted diffusion', 'diffusion restriction',
    'calcification', 'calcified',
    'necrosis', 'necrotic',
    'cystic change', 'cystic component',
}

TEMPORAL_MODIFIER_QUALIFIERS: set[str] = {
    'acute', 'active', 'significant', 'new', 'interval',
}

def is_modifier_between(text: str, neg_end: int, target_start: int) -> tuple[bool, str]:
    """
    Check if a known modifier term appears between the negation cue end and the target start.
    
    Args:
        text: The clause text.
        neg_end: End index of the negation cue.
        target_start: Start index of the target term.
        
    Returns:
        tuple[bool, str]: (is_modifier, modifier_term)
    """
    if neg_end > target_start:
        return False, ""
        
    between_text = text[neg_end:target_start].lower()
    
    for modifier in sorted(MODIFIER_TERMS, key=len, reverse=True):
        if re.search(rf'\b{re.escape(modifier)}\b', between_text):
            return True, modifier
            
    return False, ""
