"""
Stretch goal — synthetic FHIR generator for borderline cases.
Builds patients whose lab values sit exactly at, or just to either
side of, the thresholds your sample protocol actually checks
(eGFR > 60, HbA1c <= 9.0, 14-day GLP-1 washout) — the cases most
likely to flip a Screening Agent decision, and therefore the most
useful ones to stress-test matcher.py against.

Run from repo root:
    python data/generate_borderline_fhir.py
Writes FHIR Bundles to data/synthetic_ehr_fhir/, loadable via the
existing POST /ingest/patient endpoint.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.fhir_converter import record_to_fhir_bundle

OUT_DIR = Path(__file__).resolve().parent / "synthetic_ehr_fhir"
OUT_DIR.mkdir(exist_ok=True)

BORDERLINE_CASES = [
    {
        "patient_id": "SYN-BORDER-001", "age": 52, "sex": "female",
        "labs": {"eGFR": 60.1, "HbA1c": 9.0},   # just inside both thresholds
        "conditions": ["Type 2 Diabetes Mellitus"], "medications": ["Metformin"],
        "pregnant": False, "last_glp1_dose_days_ago": 14,  # exactly at washout boundary
    },
    {
        "patient_id": "SYN-BORDER-002", "age": 61, "sex": "male",
        "labs": {"eGFR": 59.9, "HbA1c": 9.0},   # eGFR just fails
        "conditions": ["Type 2 Diabetes Mellitus"], "medications": ["Metformin"],
        "pregnant": False, "last_glp1_dose_days_ago": 14,
    },
    {
        "patient_id": "SYN-BORDER-003", "age": 47, "sex": "female",
        "labs": {"eGFR": 75.0, "HbA1c": 9.1},   # HbA1c just fails
        "conditions": ["Type 2 Diabetes Mellitus"], "medications": ["Metformin"],
        "pregnant": False, "last_glp1_dose_days_ago": 15,
    },
    {
        "patient_id": "SYN-BORDER-004", "age": 55, "sex": "male",
        "labs": {"eGFR": 68.0, "HbA1c": 7.8},
        "conditions": ["Type 2 Diabetes Mellitus"], "medications": ["Metformin"],
        "pregnant": False, "last_glp1_dose_days_ago": 13,  # 1 day short of washout — should fail
    },
]


def main():
    for record in BORDERLINE_CASES:
        bundle = record_to_fhir_bundle(record)
        out_path = OUT_DIR / f"{record['patient_id']}.fhir.json"
        out_path.write_text(json.dumps(bundle, indent=2))
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
