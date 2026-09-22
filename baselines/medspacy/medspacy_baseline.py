"""medspaCy ConText baseline for MR-RATE 32 target pathologies.

Uses standard medspaCy components:
- medspacy_target_matcher loaded with TargetRule objects from the canonical concept dictionary
- medspacy_context loaded with standard ConText modifiers for English
- Extraction of ConText attributes:
    - is_negated
    - is_uncertain / is_hypothetical
    - is_historical
- Deterministic conversion to MR-RATE assertion states using the frozen mapping:
    AFFIRMED_CURRENT -> S
    UNCERTAIN        -> UC
    HISTORICAL       -> H
    NEGATED          -> C
    TARGET_NOT_FOUND -> U
- Document Precedence: S > UC > H > C > U
- No D1 rescue/exclusion rules or label overrides are applied.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

# Prevent local directory shadowing installed medspacy package
parent_dir = str(Path(__file__).resolve().parent.parent)
sys_path_had_parent = False
if parent_dir in sys.path:
    sys.path.remove(parent_dir)
    sys_path_had_parent = True

import medspacy
from medspacy.target_matcher import TargetRule
from loguru import logger

if sys_path_had_parent:
    sys.path.insert(0, parent_dir)

# Silence PyRuSH debug logging
logger.disable("PyRuSH")




class MedspaCyBaseline:
    def __init__(
        self,
        concept_dictionary_path: Optional[Path] = None,
    ):
        base_dir = Path(__file__).resolve().parent
        if concept_dictionary_path is None:
            concept_dictionary_path = base_dir.parent / "mappings" / "concept_dictionary.json"

        with open(concept_dictionary_path, "r", encoding="utf-8") as f:
            self.concept_dict: Dict[str, Any] = json.load(f)

        # Load medspaCy pipeline with target matcher and context
        self.nlp = medspacy.load()
        self.target_matcher = self.nlp.get_pipe("medspacy_target_matcher")

        # Register TargetRules for all 32 labels
        rules = []
        for canonical, entry in self.concept_dict.items():
            variants = entry.get("variants", [canonical])
            for v in variants:
                rules.append(
                    TargetRule(
                        literal=v,
                        category=canonical,
                    )
                )
        self.target_matcher.add(rules)

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
                "baseline": "medspacy",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "empty_report",
            }

        doc = self.nlp(report_text)

        # Find entities matching target_pathology
        target_ents = [ent for ent in doc.ents if ent.label_ == target_pathology]

        if not target_ents:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "medspacy",
                "decision": "U",
                "target_detected": False,
                "negated": False,
                "uncertain": False,
                "historical": False,
                "matched_text": "",
                "modifier_text": "",
                "reason": "target_not_found",
            }

        classified_mentions = []
        for ent in target_ents:
            is_neg = bool(ent._.is_negated)
            is_unc = bool(ent._.is_uncertain or getattr(ent._, "is_hypothetical", False))
            is_hist = bool(ent._.is_historical)

            modifiers = []
            if hasattr(ent._, "modifiers") and ent._.modifiers:
                for mod in ent._.modifiers:
                    modifiers.append(mod.text if hasattr(mod, "text") else str(mod))

            if is_neg:
                assertion = "NEGATED"
            elif is_unc:
                assertion = "UNCERTAIN"
            elif is_hist:
                assertion = "HISTORICAL"
            else:
                assertion = "AFFIRMED_CURRENT"

            classified_mentions.append({
                "matched_text": ent.text,
                "assertion": assertion,
                "is_negated": is_neg,
                "is_uncertain": is_unc,
                "is_historical": is_hist,
                "modifier_text": "; ".join(modifiers),
            })

        affirmed = [m for m in classified_mentions if m["assertion"] == "AFFIRMED_CURRENT"]
        uncertain = [m for m in classified_mentions if m["assertion"] == "UNCERTAIN"]
        historical = [m for m in classified_mentions if m["assertion"] == "HISTORICAL"]
        negated = [m for m in classified_mentions if m["assertion"] == "NEGATED"]

        if affirmed:
            return {
                "case_id": case_id,
                "target_pathology": target_pathology,
                "baseline": "medspacy",
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
                "baseline": "medspacy",
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
                "baseline": "medspacy",
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
                "baseline": "medspacy",
                "decision": "C",
                "target_detected": True,
                "negated": True,
                "uncertain": False,
                "historical": False,
                "matched_text": "; ".join(m["matched_text"] for m in negated),
                "modifier_text": "; ".join(filter(None, (m["modifier_text"] for m in negated))),
                "reason": f"all_mentions_negated ({len(negated)} negated)",
            }
