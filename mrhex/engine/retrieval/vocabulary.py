def terms_for_entry(entry: dict) -> list[str]:
    """
    Extract and clean vocabulary terms from a rule entry.
    
    Args:
        entry: A dictionary containing the pathology configuration.
        
    Returns:
        A deduplicated list of cleaned positive terms.
    """
    if not entry or 'machine_rules' not in entry:
        return []
    terms = list(entry['machine_rules'].get('positive_terms', []))
    surface_forms = entry['machine_rules'].get('surface_forms', [])
    if surface_forms:
        terms.extend(surface_forms)
    
    cleaned_terms = []
    for term in terms:
        cleaned = str(term).strip()
        cleaned = " ".join(cleaned.split())
        if cleaned:
            cleaned_terms.append(cleaned)
            
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for term in cleaned_terms:
        if term not in seen:
            seen.add(term)
            deduped.append(term)
            
    return deduped
