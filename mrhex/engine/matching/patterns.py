import re

def compile_pattern(term: str) -> re.Pattern:
    """Compile a vocabulary term into a robust regex pattern."""
    return re.compile(
        r'(?<!\w)' + re.escape(term).replace(r'\ ', r'[\s-]+') + r'(?!\w)',
        re.I
    )

def find_all_matches(text: str, terms: list[str]) -> list[tuple[int, int, str, str]]:
    """
    Find all matches for a list of terms in the text.
    Implements longest-match-first extraction and strict containment deduplication.
    
    Args:
        text: The source text to search in.
        terms: A list of vocabulary terms to search for.
        
    Returns:
        List of tuples (start, end, matched_text, vocabulary_term) sorted by start position.
    """
    if not text or not terms:
        return []

    # Sort terms by length descending for longest-match-first extraction
    sorted_terms = sorted(terms, key=len, reverse=True)
    
    raw_matches = []
    for term in sorted_terms:
        pattern = compile_pattern(term)
        for found in pattern.finditer(text):
            raw_matches.append((found.start(), found.end(), found.group(), term))
            
    # Sort matches by length of match descending, then by start position
    raw_matches.sort(key=lambda x: (x[1] - x[0], -x[0]), reverse=True)
    
    deduped_matches = []
    for match in raw_matches:
        start, end, _, _ = match
        is_contained = False
        
        # Strict containment deduplication: if shorter match is fully contained within a longer one
        for keep_start, keep_end, _, _ in deduped_matches:
            if start >= keep_start and end <= keep_end:
                is_contained = True
                break
                
        if not is_contained:
            deduped_matches.append(match)
            
    # Return sorted by start position
    return sorted(deduped_matches, key=lambda x: x[0])
