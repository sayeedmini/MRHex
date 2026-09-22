"""Clause splitting and coordination resolution."""
from __future__ import annotations

import re

from mrhex.engine.types import ReasonCode

# Adversative conjunctions and semicolons act as strict clause boundaries.
CLAUSE_BOUNDARY = re.compile(r"(?:,\s*)?\b(?:but|however|although|whereas|while)\b|;", re.I)

# Coordinating conjunctions and negations for ambiguity checks.
COORDINATION = re.compile(r"\b(and|or)\b", re.I)
NEGATION = re.compile(r"\b(no|not|without|negative for|absent|absence of|free of)\b", re.I)


def split_clauses(sentence: str) -> list[tuple[str, int, int]]:
    """Split a sentence into clauses based on strict boundaries.
    
    Args:
        sentence: The sentence text.
        
    Returns:
        List of tuples: (clause_text, start_in_sentence, end_in_sentence).
    """
    if not sentence:
        return []
        
    boundaries = [(0, 0)] + [(m.start(), m.end()) for m in CLAUSE_BOUNDARY.finditer(sentence)] + [(len(sentence), len(sentence))]
    
    clauses = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i][1] if i > 0 else 0
        end = boundaries[i + 1][0]
        
        if start < end:
            clause_text = sentence[start:end]
            if clause_text.strip():
                clauses.append((clause_text, start, end))
                
    return clauses


def clause_for_offset(sentence: str, sentence_start: int, offset: int) -> tuple[str, int, int]:
    """Find the clause containing the given absolute offset.
    
    Args:
        sentence: The text of the sentence.
        sentence_start: The absolute starting offset of the sentence in the document.
        offset: The absolute target offset to locate.
        
    Returns:
        Tuple of (clause_text, absolute_start, absolute_end).
    """
    rel_offset = offset - sentence_start
    
    for clause_text, start, end in split_clauses(sentence):
        if start <= rel_offset < end:
            return clause_text, sentence_start + start, sentence_start + end
            
    # Fallback to the whole sentence if not found within a clause
    return sentence, sentence_start, sentence_start + len(sentence)


def is_coordination_ambiguous(sentence: str, target_start: int = -1, target_end: int = -1) -> bool:
    """Determine if coordination in the sentence creates ambiguous attachment to the target.
    
    Do NOT mark a sentence ambiguous merely because it contains 'and' or 'or'.
    
    Safe cases that must NOT route:
    - Target followed by coordinated modifiers: 'Meningioma with edema and mass effect.'
    - Target followed by coordinated negated modifiers: 'Meningioma without edema or mass effect.'
    - Direct coordinated negation: 'No hemorrhage or mass effect.'
    - Multiple negated clauses: 'No edema and no midline shift.'
    
    Routing is required only when attachment to the TARGET assertion is truly ambiguous:
    - Ambiguous scope around question marks or conditional clauses.
    - Telegraphic mixed-polarity lists where cue attachment to target is unclear.
    """
    coord_matches = list(COORDINATION.finditer(sentence))
    if not coord_matches:
        return False

    # Check for question marks or conditional phrasing in sentence near coordination
    if "?" in sentence:
        return True
    if re.search(r"\b(if|whether|evaluate\s+if)\b", sentence, re.I):
        if target_start >= 0:
            target_clause, _, _ = clause_for_offset(sentence, 0, target_start)
            if not re.search(r"\b(if|whether|evaluate\s+if)\b", target_clause, re.I):
                if re.search(r"\b(definitely\s+present|present|noted|identified)\b", target_clause, re.I):
                    return False
        return True

    if target_start < 0 or target_end < 0:
        # Fallback if target position is unknown
        has_neg = bool(NEGATION.search(sentence))
        has_pos = bool(re.search(r"\b(present|noted|identified|seen)\b", sentence, re.I))
        return has_neg and has_pos

    # Target-local coordination analysis:
    # 1. Target followed by prepositional modifier coordination:
    #    e.g., "<target> with/without/showing X and/or Y"
    after_target = sentence[target_end:]
    prep_match = re.match(
        r"^\s*(?:with|without|showing|demonstrating|having|associated\s+with|characterized\s+by)\b",
        after_target,
        re.I,
    )
    if prep_match:
        # Coordination is within post-target modifier complement; target assertion is unambiguous
        return False

    # 2. Check if target is governed by a preceding negation cue
    neg_matches = list(NEGATION.finditer(sentence))
    preceding_negs = [n for n in neg_matches if n.end() <= target_start]
    if preceding_negs:
        neg = preceding_negs[-1]
        between = sentence[neg.end():target_start]
        words = re.findall(r"\b\w+\b", between)
        if len(words) <= 5 and not re.search(r"[;:]", between):
            return False

    # 3. Check for mixed polarity across coordination directly involving target
    for coord in coord_matches:
        coord_start, coord_end = coord.start(), coord.end()
        if coord_start < target_start:
            left_text = sentence[:coord_start]
            right_text = sentence[coord_end:target_end]
            if NEGATION.search(left_text) and not NEGATION.search(right_text):
                if re.search(r"\b(is|are|was|were|present|noted|identified)\b", right_text, re.I):
                    return True

    return False

