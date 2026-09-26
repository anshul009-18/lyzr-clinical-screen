"""
Phase 4b — Medical Safety Agent.
Deterministic ontology cross-check against a curated SNOMED-CT / ICD-10 /
LOINC lookup table. Two jobs:
  1. Flag condition/medication terms with no known ontology mapping
     ("unmapped term" — could be a typo, a non-standard abbreviation,
     or a real concept this lookup just doesn't cover yet).
  2. Flag terms that DO map to a known concept via a synonym the
     Screening Agent's plain substring match (agents/screening_agent/
     matcher.py::CONDITION_KEYWORD_FIELDS) would NOT catch — this is
     the "terminology mismatch the matcher might miss" case, and it's
     the whole reason this agent exists as a second, independent check
     rather than folding into matcher.py.
Called from agents/orchestration/pipeline.py::run_medical_safety.
"""

from typing import Optional

# --- Condition ontology: canonical concept + synonyms + cross-refs -----
# `matcher_keyword` = the exact substring agents/screening_agent/matcher.py
# checks for in CONDITION_KEYWORD_FIELDS. Kept in sync deliberately so this
# validator can detect drift between the two.
CONDITION_ONTOLOGY = [
    {
        "snomed": "46635009", "icd10": "E10", "canonical": "Type 1 Diabetes Mellitus",
        "matcher_keyword": "type 1 diabetes",
        "synonyms": {"type 1 diabetes", "type 1 diabetes mellitus", "diabetes mellitus type 1",
                     "t1dm", "insulin-dependent diabetes mellitus", "iddm"},
    },
    {
        "snomed": "44054006", "icd10": "E11", "canonical": "Type 2 Diabetes Mellitus",
        "matcher_keyword": None,  # matcher.py doesn't check this one — informational only
        "synonyms": {"type 2 diabetes", "type 2 diabetes mellitus", "diabetes mellitus type 2",
                     "t2dm", "non-insulin-dependent diabetes mellitus", "niddm"},
    },
    {
        "snomed": "420422005", "icd10": "E10.1", "canonical": "Diabetic Ketoacidosis",
        "matcher_keyword": "diabetic ketoacidosis",
        "synonyms": {"diabetic ketoacidosis", "dka", "ketoacidosis, diabetic"},
    },
    {
        "snomed": "75694006", "icd10": "K85", "canonical": "Acute or Chronic Pancreatitis",
        "matcher_keyword": "pancreatitis",
        "synonyms": {"pancreatitis", "acute pancreatitis", "chronic pancreatitis"},
    },
    {
        "snomed": "414916001", "icd10": "E66", "canonical": "Obesity",
        "matcher_keyword": None,
        "synonyms": {"obesity", "obese"},
    },
    {
        "snomed": "55822004", "icd10": "E78.5", "canonical": "Hyperlipidemia",
        "matcher_keyword": None,
        "synonyms": {"hyperlipidemia", "hyperlipidaemia", "dyslipidemia"},
    },
]

# --- Lab ontology: LOINC code + physiologically plausible range --------
# Range check is a data-quality sanity gate, not a clinical judgment call —
# flags impossible values (unit errors, transcription errors) for review.
LAB_ONTOLOGY = {
    "egfr": {"loinc": "62238-1", "canonical": "eGFR", "plausible_range": (0, 200)},
    "hba1c": {"loinc": "4548-4", "canonical": "HbA1c", "plausible_range": (2.0, 20.0)},
}

# --- Medication reference: NOT a formal ontology, see config.yaml note --
MEDICATION_REFERENCE = {"metformin", "semaglutide", "liraglutide", "dulaglutide", "insulin"}


def _match_condition(raw_term: str) -> Optional[dict]:
    """Exact or substring synonym match against CONDITION_ONTOLOGY. Deterministic
    string comparison only — no fuzzy/NLP matching, so a miss here is a real
    signal, not noise."""
    term = raw_term.lower().strip()
    for entry in CONDITION_ONTOLOGY:
        if term in entry["synonyms"]:
            return entry
        if any(syn in term for syn in entry["synonyms"]):
            return entry
    return None


def validate(record: dict) -> tuple[bool, Optional[str]]:
    """
    Returns (flagged, reason). flagged=True routes the pipeline to
    REQUIRES_HUMAN_REVIEW regardless of what the Screening Agent decided —
    this agent can only add caution, never override an INELIGIBLE/ELIGIBLE
    decision into something more permissive.
    """
    issues: list[str] = []

    # 1. Conditions — ontology mapping + matcher-blind-spot check
    for raw in record.get("conditions") or []:
        entry = _match_condition(raw)
        if entry is None:
            issues.append(f"Unmapped condition term (no SNOMED/ICD-10 concept found): '{raw}'")
            continue

        keyword = entry["matcher_keyword"]
        if keyword and keyword not in raw.lower():
            issues.append(
                f"'{raw}' maps to {entry['canonical']} (SNOMED {entry['snomed']}, ICD-10 "
                f"{entry['icd10']}) but does not contain matcher's keyword '{keyword}' — "
                f"Screening Agent's substring check would silently miss this"
            )

    # 2. Labs — LOINC-tagged plausibility check
    labs = record.get("labs") or {}
    for key, value in labs.items():
        if value is None:
            continue
        ref = LAB_ONTOLOGY.get(key.lower())
        if ref is None:
            issues.append(f"Unmapped lab field (no LOINC mapping found): '{key}'")
            continue
        low, high = ref["plausible_range"]
        if not (low <= value <= high):
            issues.append(
                f"{ref['canonical']} (LOINC {ref['loinc']}) value {value} outside "
                f"plausible range [{low}, {high}] — possible unit or entry error"
            )

    # 3. Medications — reference-list check
    for med in record.get("medications") or []:
        if med.lower().strip() not in MEDICATION_REFERENCE:
            issues.append(f"Unmapped medication term (not in reference list): '{med}'")

    if issues:
        return True, "; ".join(issues)
    return False, None
