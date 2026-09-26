"""
Stretch goal — Synthetic FHIR generator / converter.
Converts between this project's internal PatientRecord dict shape
and a minimal FHIR R4 Bundle (Patient + Observation + Condition +
MedicationStatement resources), so borderline synthetic patients can
be authored as valid FHIR and fed through the same POST /ingest/patient
endpoint as any other file.

Deliberately minimal FHIR — enough structure to be a recognizable,
loadable Bundle, not a full FHIR implementation.
"""

import uuid
from typing import Any

LOINC = {"eGFR": "62238-1", "HbA1c": "4548-4"}


def record_to_fhir_bundle(record: dict) -> dict:
    patient_id = record["patient_id"]
    entries = []

    patient_resource = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [{"system": "urn:lyzr-clinical-screen:patient-id", "value": patient_id}],
        "gender": (record.get("sex") or "unknown").lower(),
    }
    if record.get("age") is not None:
        patient_resource["extension"] = [{
            "url": "http://lyzr-clinical-screen/synthetic-age",
            "valueInteger": record["age"],
        }]
    entries.append({"resource": patient_resource})

    for lab_name, value in (record.get("labs") or {}).items():
        if value is None:
            continue
        loinc = LOINC.get(lab_name)
        entries.append({"resource": {
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": loinc, "display": lab_name}] if loinc else [],
                "text": lab_name,
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueQuantity": {"value": value},
        }})

    for condition in record.get("conditions") or []:
        entries.append({"resource": {
            "resourceType": "Condition",
            "id": str(uuid.uuid4()),
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {"text": condition},
        }})

    for med in record.get("medications") or []:
        entries.append({"resource": {
            "resourceType": "MedicationStatement",
            "id": str(uuid.uuid4()),
            "subject": {"reference": f"Patient/{patient_id}"},
            "medicationCodeableConcept": {"text": med},
        }})

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "id": str(uuid.uuid4()),
        "entry": entries,
        # Not standard FHIR — carried through so the bundle round-trips
        # back into a full PatientRecord via fhir_bundle_to_record()
        # without losing fields this minimal mapping has no proper
        # FHIR home for.
        "_synthetic_extras": {
            "pregnant": record.get("pregnant"),
            "last_glp1_dose_days_ago": record.get("last_glp1_dose_days_ago"),
        },
    }


def fhir_bundle_to_record(bundle: dict, fallback_id: str | None = None) -> dict:
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("Not a FHIR Bundle (resourceType != 'Bundle')")

    record: dict[str, Any] = {"labs": {}, "conditions": [], "medications": []}

    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        rtype = res.get("resourceType")

        if rtype == "Patient":
            record["patient_id"] = res.get("id") or fallback_id
            record["sex"] = res.get("gender")
            for ext in res.get("extension", []):
                if ext.get("url", "").endswith("synthetic-age"):
                    record["age"] = ext.get("valueInteger")

        elif rtype == "Observation":
            code_text = (res.get("code") or {}).get("text", "")
            value = (res.get("valueQuantity") or {}).get("value")
            if code_text and value is not None:
                record["labs"][code_text] = value

        elif rtype == "Condition":
            text = (res.get("code") or {}).get("text")
            if text:
                record["conditions"].append(text)

        elif rtype == "MedicationStatement":
            text = (res.get("medicationCodeableConcept") or {}).get("text")
            if text:
                record["medications"].append(text)

    extras = bundle.get("_synthetic_extras", {})
    record["pregnant"] = extras.get("pregnant")
    record["last_glp1_dose_days_ago"] = extras.get("last_glp1_dose_days_ago")

    if not record.get("patient_id"):
        record["patient_id"] = fallback_id or str(uuid.uuid4())

    return record
