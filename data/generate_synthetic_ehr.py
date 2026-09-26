"""
Synthetic EHR generator for lyzr-clinical-screen.

Generates fake-but-realistic patient records for local testing of:
  - the ingestion layer (Phase 1)
  - the PHI scrubbing agent (Phase 3) — records deliberately contain
    identifiers (name, DOB, MRN, address, phone) so you can verify
    they are actually redacted downstream
  - the screening agent (Phase 4) — lab values are randomized around
    clinically plausible ranges, including some that intentionally
    fail eligibility criteria, so ELIGIBLE / INELIGIBLE /
    REQUIRES_HUMAN_REVIEW all get exercised

No real patient data is used anywhere in this file or its output.

Usage:
    python generate_synthetic_ehr.py --count 10 --out synthetic_ehr/
"""

import argparse
import json
import random
from pathlib import Path

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

CONDITIONS_POOL = [
    "Type 2 Diabetes Mellitus",
    "Hypertension",
    "Hyperlipidemia",
    "Chronic Kidney Disease Stage 2",
    "Obesity",
]

MEDICATIONS_POOL = [
    "Metformin",
    "Lisinopril",
    "Atorvastatin",
    "GLP-1 Receptor Agonist",
    "Insulin Glargine",
]


def make_patient(patient_num: int) -> dict:
    dob = fake.date_of_birth(minimum_age=18, maximum_age=80)
    age = 2026 - dob.year

    # Intentionally spread lab values across pass/borderline/fail
    # ranges relative to the sample protocol's criteria, so the
    # screening agent has real cases to differentiate.
    egfr = round(random.uniform(35, 110), 1)          # protocol wants > 60
    hba1c = round(random.uniform(6.0, 11.5), 1)        # protocol wants 7.0-10.0
    on_glp1_days_ago = random.choice([3, 10, 14, 30, None])
    pregnant = random.random() < 0.05

    return {
        "patient_id": f"SYN-{patient_num:04d}",
        # --- PHI: must be redacted by Phase 3 before any inference ---
        "name": fake.name(),
        "dob": dob.isoformat(),
        "mrn": f"MRN-{fake.unique.random_number(digits=6)}",
        "address": fake.address().replace("\n", ", "),
        "phone": fake.phone_number(),
        "email": fake.email(),
        # --- Clinical data ---
        "age": age,
        "sex": random.choice(["male", "female"]),
        "labs": {
            "eGFR": egfr,
            "HbA1c": hba1c,
        },
        "conditions": random.sample(CONDITIONS_POOL, k=random.randint(1, 3)),
        "medications": random.sample(MEDICATIONS_POOL, k=random.randint(0, 2)),
        "pregnant": pregnant,
        "last_glp1_dose_days_ago": on_glp1_days_ago,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--out", type=str, default="synthetic_ehr")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, args.count + 1):
        patient = make_patient(i)
        out_path = out_dir / f"patient_{i:03d}.json"
        out_path.write_text(json.dumps(patient, indent=2, default=str))
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
