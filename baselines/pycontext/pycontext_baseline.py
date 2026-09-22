"""pyConTextNLP baseline for MR-RATE 32 target pathologies.

Uses pyConTextNLP (Chapman et al.) to extract targets and contextual modifiers
(negation, uncertainty, historical/temporality) via directional context graph.

Compatibility Note:
pyConTextNLP 0.7.0.1 expects NetworkX 1.x where G.predecessors() returned a list.
In modern NetworkX (3.x), G.predecessors() returns an iterator without a .sort() method.
We adapt ConTextMarkup.getModifiers to convert the iterator to a list before sorting:
    modifiers = sorted(list(self.predecessors(node)))
No algorithms or rules of pyConTextNLP are altered.

Decision Logic (Frozen MR-RATE assertion mapping):
    AFFIRMED_CURRENT  -> S
    UNCERTAIN         -> UC
    HISTORICAL        -> H
    NEGATED           -> C
    TARGET_NOT_FOUND  -> U
    Document Precedence: S > UC > H > C > U
"""

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

import pyConTextNLP.itemData as itemData
import pyConTextNLP.pyConText as pyConText

# Modern NetworkX compatibility bridge: ensure iterator is converted to list before sorting
pyConText.ConTextMarkup.getModifiers = lambda self, node: sorted(list(self.predecessors(node)))


class PyConTextBaseline:
    def __init__(
        self,
        concept_dictionary_path: Optional[Path] = None,
        modifiers_path: Optional[Path] = None,
    ):
        base_dir = Path(__file__).resolve().parent
        if concept_dictionary_path is None:
            concept_dictionary_path = base_dir.parent / "mappings" / "concept_dictionary.json"
        if modifiers_path is None:
            modifiers_path = base_dir / "pycontext_modifiers.tsv"

        with open(concept_dictionary_path, "r", encoding="utf-8") as f:
            self.concept_dict: Dict[str, Any] = json.load(f)

        # Load modifiers from TSV
        self.modifiers = []
        with open(modifiers_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                literal = row["literal"].strip()
                category = row["category"].strip()
                regex = row["regex"].strip()
                rule = row["rule"].strip()
                if literal and category:
                    item = itemData.contextItem([literal, category, regex, rule])
                    self.modifiers.append(item)

        # Pre-build target contextItems per canonical label
        self.targets_by_label: Dict[str, List[itemData.contextItem]] = {}
        for canonical, entry in self.concept_dict.items():
            items = []
            variants = entry.get("variants", [canonical])
            for v in sorted(variants, key=len, reverse=True):
                escaped = re.escape(v)
                pattern = rf"\b{escaped}\b"
                items.append(itemData.contextItem([v, "target", pattern, ""]))
            self.targets_by_label[canonical] = items

    def split_sentences(self, text: str) -> List[str]:
        raw_sentences = re.split(r"(?<=[.!?\n;])\s+", text)
        return [s.strip() for s in raw_sentences if s.strip()]

    def process_sentence(
        self, sentence: str, target_items: List[itemData.contextItem]
    ) -> List[Dict[str, Any]]:
        markup = pyConText.ConTextMarkup()
        markup.setRawText(sentence)
        markup.cleanText()
        markup.markItems(self.modifiers, mode="modifier")
        markup.markItems(target_items, mode="target")
        markup.pruneMarks()
        markup.dropMarks("modifier")
        markup.applyModifiers()

        results = []
        for node in markup.nodes():
            if "target" in node.getCategory():
                mod_objs = markup.getModifiers(node)
                categories = []
                mod_phrases = []
                for m in mod_objs:
                    categories.extend(m.getCategory())
                    mod_phrases.append(m.getPhrase())

                # Classify single mention assertion:
                # Standard ConText hierarchy: Negation > Uncertainty > Historical > Affirmed
                is_negated = any(
                    c in ("definite_negated_existence", "probable_negated_existence")
                    for c in categories
                )
                is_uncertain = any(
                    c in ("probable_possible", "uncertain", "possible_existence", "probable_existence")
                    for c in categories
                )
                is_historical = any(
                    c in ("historical", "past") for c in categories
                )

                if is_negated:
                    assertion = "NEGATED"
                elif is_uncertain:
                    assertion = "UNCERTAIN"
                elif is_historical:
                    assertion = "HISTORICAL"
                else:
                    assertion = "AFFIRMED_CURRENT"

                results.append({
                    "matched_text": node.getPhrase(),
                    "assertion": assertion,
                    "is_negated": is_negated,
                    "is_uncertain": is_uncertain,
                    "is_historical": is_historical,
                    "modifier_text": "; ".join(mod_phrases),
                })
        return results

    def process_report(
        self,
        report_text: str,
        target_pathology: str,
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a single report for a target pathology.

        Deterministic Precedence (Codebook & frozen assertion mapping):
        1. If any mention is AFFIRMED_CURRENT -> S
        2. Else if any mention is UNCERTAIN -> UC
        3. Else if any mention is HISTORICAL -> H
        4. Else if all mentions are NEGATED -> C
        5. If no mentions found -> U
        """
        if not report_text or not isinstance(report_text, str):
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "empty_report",
            }

        target_items = self.targets_by_label.get(target_pathology, [])
        if not target_items:
            # Fallback if label not in dictionary
            escaped = re.escape(target_pathology)
            target_items = [itemData.contextItem([target_pathology, "target", rf"\b{escaped}\b", ""])]

        sentences = self.split_sentences(report_text)
        all_mentions = []
        for sent in sentences:
            mentions = self.process_sentence(sent, target_items)
            all_mentions.extend(mentions)

        if not all_mentions:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "target_not_found",
            }

        # Document Precedence resolution
        affirmed = [m for m in all_mentions if m["assertion"] == "AFFIRMED_CURRENT"]
        uncertain = [m for m in all_mentions if m["assertion"] == "UNCERTAIN"]
        historical = [m for m in all_mentions if m["assertion"] == "HISTORICAL"]
        negated = [m for m in all_mentions if m["assertion"] == "NEGATED"]

        if affirmed:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "S",
                "target_detected": True,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in affirmed),
                "modifier_text": "",
                "reason": f"affirmed_mention ({len(affirmed)} affirmed, {len(uncertain)} uncertain, {len(historical)} historical, {len(negated)} negated)",
            }
        elif uncertain:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "UC",
                "target_detected": True,
                "negated": False,
                "uncertain": True,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in uncertain),
                "modifier_text": "; ".join(filter(None, (m["modifier_text"] for m in uncertain))),
                "reason": f"uncertain_mention ({len(uncertain)} uncertain, {len(historical)} historical, {len(negated)} negated)",
            }
        elif historical:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "H",
                "target_detected": True,
                "negated": False,
                "uncertain": False,
                "historical": True,
                "matched_text": "; ".join(m["matched_text"] for m in historical),
                "modifier_text": "; ".join(filter(None, (m["modifier_text"] for m in historical))),
                "reason": f"historical_mention ({len(historical)} historical, {len(negated)} negated)",
            }
        else:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "pycontext",
                "decision": "C",
                "target_detected": True,
                "negated": True,
                "uncertain": False,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in negated),
                "modifier_text": "; ".join(filter(None, (m["modifier_text"] for m in negated))),
                "reason": f"all_mentions_negated ({len(negated)} negated)",
            }
