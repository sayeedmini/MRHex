"""NegEx-style clinical negation baseline for MR-RATE 32 target pathologies.

Based on the standard NegEx algorithm (Chapman et al., 2001):
- Concept matching against the frozen canonical concept dictionary
- Directional pre- and post-negation trigger identification
- Pseudo-negation suppression
- Conjunction / termination boundary termination
- Directional token window scoping (default 6 tokens within the same sentence)
- Frozen MR-RATE mapping:
    AFFIRMED_CURRENT -> S
    NEGATED          -> C
    TARGET_NOT_FOUND -> U
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml


# Standard NegEx triggers (Chapman et al., 2001 & Kit NegEx trigger definitions)
PRE_NEGATION_TRIGGERS = [
    "no evidence of",
    "no sign of",
    "no signs of",
    "no indication of",
    "no suggestion of",
    "no definite evidence of",
    "no definite",
    "negative for",
    "free of",
    "absence of",
    "denies",
    "denied",
    "rules out",
    "ruled out",
    "rule out",
    "unremarkable for",
    "with no",
    "without any",
    "without evidence of",
    "without signs of",
    "without",
    "no",
    "not seen",
    "not identified",
    "not visualized",
    "not detected",
    "not present",
    "never had",
    "zero",
]

POST_NEGATION_TRIGGERS = [
    "was ruled out",
    "is ruled out",
    "ruled out",
    "was negative",
    "is negative",
    "unlikely",
    "not seen",
    "not identified",
    "not visualized",
    "not detected",
    "not present",
    "free",
]

PSEUDO_NEGATION_TRIGGERS = [
    "no change",
    "no significant change",
    "no interval change",
    "no increase",
    "no decrease",
    "not only",
    "without difficulty",
    "no cause for",
]

CONJUNCTION_TERMINATORS = [
    "but",
    "however",
    "nevertheless",
    "yet",
    "though",
    "although",
    "except",
    "apart from",
    "aside from",
    "secondary to",
    "as well as",
]


class NegExBaseline:
    def __init__(
        self,
        concept_dictionary_path: Optional[Path] = None,
        max_window: int = 6,
    ):
        self.max_window = max_window
        if concept_dictionary_path is None:
            concept_dictionary_path = (
                Path(__file__).resolve().parent.parent / "mappings" / "concept_dictionary.json"
            )
        with open(concept_dictionary_path, "r", encoding="utf-8") as f:
            self.concept_dict: Dict[str, Any] = json.load(f)

        # Pre-compile target regexes sorted by length descending
        self.target_patterns: Dict[str, List[Tuple[str, re.Pattern]]] = {}
        for canonical, entry in self.concept_dict.items():
            patterns = []
            variants = entry.get("variants", [canonical])
            for v in sorted(variants, key=len, reverse=True):
                # Word boundary matching
                escaped = re.escape(v)
                pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
                patterns.append((v, pattern))
            self.target_patterns[canonical] = patterns

        # Sort triggers by length descending to match multi-word triggers first
        self.pseudo_triggers = sorted(PSEUDO_NEGATION_TRIGGERS, key=len, reverse=True)
        self.pre_triggers = sorted(PRE_NEGATION_TRIGGERS, key=len, reverse=True)
        self.post_triggers = sorted(POST_NEGATION_TRIGGERS, key=len, reverse=True)
        self.terminators = sorted(CONJUNCTION_TERMINATORS, key=len, reverse=True)

    def split_sentences(self, text: str) -> List[str]:
        # Split on standard sentence terminators, keeping newlines / headings clean
        raw_sentences = re.split(r"(?<=[.!?\n;])\s+", text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        return sentences

    def tokenize(self, text: str) -> List[Tuple[str, int, int]]:
        """Tokenize sentence into list of (token_str, start_char, end_char)."""
        tokens = []
        for m in re.finditer(r"\b\w+(?:-\w+)*\b|[.,;:!?]", text):
            tokens.append((m.group(), m.start(), m.end()))
        return tokens

    def find_target_mentions(
        self, sentence: str, target_pathology: str
    ) -> List[Dict[str, Any]]:
        patterns = self.target_patterns.get(target_pathology, [])
        mentions = []
        occupied_spans: List[Tuple[int, int]] = []

        for variant_text, pattern in patterns:
            for match in pattern.finditer(sentence):
                start, end = match.span()
                # Check for overlap with already matched longer variants
                if any(s <= start and end <= e for s, e in occupied_spans):
                    continue
                occupied_spans.append((start, end))
                mentions.append({
                    "matched_text": match.group(),
                    "start": start,
                    "end": end,
                })
        return sorted(mentions, key=lambda m: m["start"])

    def evaluate_sentence_negation(
        self, sentence: str, mention: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], str]:
        """Check whether a mention in a sentence is negated via NegEx rules."""
        m_start = mention["start"]
        m_end = mention["end"]

        # 1. Mask pseudo-negations in sentence to prevent false negation triggers
        masked_sent = sentence
        for pseudo in self.pseudo_triggers:
            pattern = re.compile(rf"\b{re.escape(pseudo)}\b", re.IGNORECASE)
            masked_sent = pattern.sub(" " * len(pseudo), masked_sent)

        # 2. Check PRE-negation triggers before the mention
        pre_text = masked_sent[:m_start]
        for trigger in self.pre_triggers:
            pattern = re.compile(rf"\b{re.escape(trigger)}\b", re.IGNORECASE)
            for tm in pattern.finditer(pre_text):
                t_start, t_end = tm.span()
                between_text = masked_sent[t_end:m_start]

                # Check if a terminator/conjunction interrupts the scope
                terminated = False
                for term in self.terminators:
                    if re.search(rf"\b{re.escape(term)}\b", between_text, re.IGNORECASE):
                        terminated = True
                        break
                if terminated:
                    continue

                # Check token distance
                tokens_between = len(re.findall(r"\b\w+\b", between_text))
                if tokens_between <= self.max_window:
                    return True, sentence[t_start:t_end], f"pre_negation_within_{tokens_between}_tokens"

        # 3. Check POST-negation triggers after the mention
        post_text = masked_sent[m_end:]
        for trigger in self.post_triggers:
            pattern = re.compile(rf"\b{re.escape(trigger)}\b", re.IGNORECASE)
            for tm in pattern.finditer(post_text):
                t_start = m_end + tm.start()
                t_end = m_end + tm.end()
                between_text = masked_sent[m_end:t_start]

                # Check terminator
                terminated = False
                for term in self.terminators:
                    if re.search(rf"\b{re.escape(term)}\b", between_text, re.IGNORECASE):
                        terminated = True
                        break
                if terminated:
                    continue

                # Token distance
                tokens_between = len(re.findall(r"\b\w+\b", between_text))
                if tokens_between <= self.max_window:
                    return True, sentence[t_start:t_end], f"post_negation_within_{tokens_between}_tokens"

        return False, None, "affirmed"

    def process_report(
        self,
        report_text: str,
        target_pathology: str,
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a single report for a single target pathology.

        Document Precedence (Codebook & frozen assertion mapping):
        - If any mention is affirmed -> S
        - Else if all mentions are negated -> C
        - Else if no mentions found -> U
        """
        if not report_text or not isinstance(report_text, str):
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "negex",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "empty_report",
            }

        sentences = self.split_sentences(report_text)
        all_mentions = []

        for sent in sentences:
            mentions = self.find_target_mentions(sent, target_pathology)
            for m in mentions:
                is_neg, mod_text, reason = self.evaluate_sentence_negation(sent, m)
                all_mentions.append({
                    "sentence": sent,
                    "matched_text": m["matched_text"],
                    "negated": is_neg,
                    "modifier_text": mod_text or "",
                    "reason": reason,
                })

        if not all_mentions:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "negex",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "target_not_found",
            }

        # Check for any affirmed mention
        affirmed_mentions = [m for m in all_mentions if not m["negated"]]
        negated_mentions = [m for m in all_mentions if m["negated"]]

        if affirmed_mentions:
            first_aff = affirmed_mentions[0]
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "negex",
                "decision": "S",
                "target_detected": True,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in affirmed_mentions),
                "modifier_text": "",
                "reason": f"affirmed_mention_found ({len(affirmed_mentions)} affirmed, {len(negated_mentions)} negated)",
            }
        else:
            first_neg = negated_mentions[0]
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "negex",
                "decision": "C",
                "target_detected": True,
                "negated": True,
                "uncertain": False,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in negated_mentions),
                "modifier_text": "; ".join(filter(None, (m["modifier_text"] for m in negated_mentions))),
                "reason": f"all_mentions_negated ({len(negated_mentions)} negated)",
            }
