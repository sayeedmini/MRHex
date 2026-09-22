"""Sentence splitting and boundary resolution."""
from __future__ import annotations

import re

# Protect decimals (1.5), abbreviations (vs., Dr., etc.), and measurement patterns with periods.
PROTECTED_PATTERN = re.compile(
    r"(?i)\b(?:vs|dr|approx|etc|no)\.|\be\.g\.|\bi\.e\.|\d+\.\d+"
)

# Sentence terminators: period, exclamation, question, and newline (semicolon is clause boundary).
SENTENCE_BOUNDARIES = re.compile(r"[^.?!\n]+(?:[.?!]|\n|$)")


def _protect_match(match: re.Match) -> str:
    """Replace periods with a placeholder of the same length to preserve offsets."""
    return match.group(0).replace(".", "\x00")


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentences, preserving character offsets.
    
    Args:
        text: The source report text.
        
    Returns:
        List of tuples: (sentence_text, start_offset, end_offset).
    """
    if not text:
        return []
        
    # Temporarily replace protected periods with \x00
    protected_text = PROTECTED_PATTERN.sub(_protect_match, text)
    
    sentences = []
    for match in SENTENCE_BOUNDARIES.finditer(protected_text):
        start = match.start()
        end = match.end()
        sentence_text = text[start:end]
        
        # Skip purely empty or whitespace-only matches
        if sentence_text.strip():
            sentences.append((sentence_text, start, end))
            
    return sentences


def sentence_for_offset(text: str, offset: int) -> tuple[str, int, int]:
    """Find the sentence containing the given character offset.
    
    Args:
        text: The source report text.
        offset: The character offset to locate.
        
    Returns:
        Tuple of (sentence_text, start_offset, end_offset).
    """
    for sent_text, start, end in split_sentences(text):
        if start <= offset < end:
            return sent_text, start, end
            
    # Fallback if out of bounds
    return text, 0, len(text)
