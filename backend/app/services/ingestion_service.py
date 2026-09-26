import json
import re
from pathlib import Path

import pdfplumber

from backend.app.models.patient import PatientRecord, PatientLabs


def extract_protocol_text(pdf_path: str) -> str:
    """Extract raw text from a clinical trial protocol PDF."""
    text_chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_chunks.append(page_text)
    return "\n".join(text_chunks)


def normalize_patient_record(raw: dict) -> PatientRecord:
    return PatientRecord(**raw)


def parse_patient_text(text: str, patient_id: str) -> PatientRecord:
    """
    Deterministic, regex-based field extraction from a plain-text or
    PDF-extracted patient/lab record. Expects loosely structured
    'Field: value' style lines, which is the common shape for lab
    reports and clinic note exports.

    Deliberately NOT agent-based — this stays deterministic so no
    LLM call is needed just to parse a structured lab report, and so
    behavior is 100% reproducible for the audit trail.
    """

    def find(pattern: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def find_float(pattern: str) -> float | None:
        val = find(pattern)
        try:
            return float(val) if val else None
        except ValueError:
            return None

    def find_int(pattern: str) -> int | None:
        val = find(pattern)
        try:
            return int(val) if val else None
        except ValueError:
            return None

    name = find(r"Name:\s*(.+)")
    dob = find(r"(?:DOB|Date of Birth):\s*([\d\-/]+)")
    mrn = find(r"MRN:?\s*(\S+)")
    address = find(r"Address:\s*(.+)")
    phone = find(r"Phone:\s*(.+)")
    email = find(r"Email:\s*(\S+)")
    age = find_int(r"Age:?\s*(\d+)")
    sex = find(r"Sex:?\s*(\w+)")
    egfr = find_float(r"eGFR:?\s*([\d.]+)")
    hba1c = find_float(r"HbA1c:?\s*([\d.]+)")

    conditions_raw = find(r"Conditions?:\s*(.+)")
    medications_raw = find(r"Medications?:\s*(.+)")
    conditions = [c.strip() for c in conditions_raw.split(",")] if conditions_raw else []
    medications = [m.strip() for m in medications_raw.split(",")] if medications_raw else []

    pregnant_raw = find(r"Pregnant:?\s*(\w+)")
    pregnant = pregnant_raw.lower() in ("yes", "true") if pregnant_raw else None

    glp1_days = find_int(r"(?:Last GLP-?1 Dose|GLP1).*?(\d+)\s*days?")

    return PatientRecord(
        patient_id=patient_id,
        name=name,
        dob=dob,
        mrn=mrn,
        address=address,
        phone=phone,
        email=email,
        age=age,
        sex=sex,
        labs=PatientLabs(eGFR=egfr, HbA1c=hba1c),
        conditions=conditions,
        medications=medications,
        pregnant=pregnant,
        last_glp1_dose_days_ago=glp1_days,
    )


def parse_patient_file(file_path: str, fallback_id: str | None = None) -> PatientRecord:
    path = Path(file_path)
    patient_id = fallback_id or path.stem

    if path.suffix == ".json":
        raw = json.loads(path.read_text())
        if raw.get("resourceType") == "Bundle":
            from backend.app.services.fhir_converter import fhir_bundle_to_record
            raw = fhir_bundle_to_record(raw, fallback_id=patient_id)
        return normalize_patient_record(raw)

    if path.suffix == ".txt":
        text = path.read_text()
        return parse_patient_text(text, patient_id=patient_id)

    if path.suffix == ".pdf":
        text = extract_protocol_text(str(path))
        if not text.strip():
            raise ValueError("No extractable text found in patient PDF (may be scanned — OCR not yet implemented)")
        return parse_patient_text(text, patient_id=patient_id)

    raise ValueError(f"Unsupported patient file format: {path.suffix}")
