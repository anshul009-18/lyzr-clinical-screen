"""
Phase 5 exit criteria:
"End-to-end test pass: run 3-5 synthetic patients through the full
pipeline, confirm outputs are sane."

Runs every synthetic patient in data/synthetic_ehr/ (currently 10,
this test uses the first 5) through: ingest protocol -> extract
criteria -> ingest patient -> generate audit dossier, and asserts
each run produced a real decision + a downloadable PDF.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = REPO_ROOT / "data" / "sample_protocols" / "protocol_001.pdf"
PATIENT_DIR = REPO_ROOT / "data" / "synthetic_ehr"

N_PATIENTS = 5


@pytest.fixture(scope="module")
def protocol_id():
    with open(PROTOCOL_PATH, "rb") as f:
        resp = client.post(
            "/ingest/protocol",
            files={"file": ("protocol_001.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200

    with open(PROTOCOL_PATH, "rb") as f:
        crit_resp = client.post(
            "/screen/extract-criteria",
            files={"file": ("protocol_001.pdf", f, "application/pdf")},
        )
    assert crit_resp.status_code == 200
    body = crit_resp.json()
    assert body["rule_count"] > 0, "Protocol Criteria Agent returned zero rules"
    return body["protocol_id"]


def _patient_files():
    files = sorted(PATIENT_DIR.glob("patient_*.json"))[:N_PATIENTS]
    assert len(files) >= 3, "Need at least 3 synthetic patients for this exit criterion"
    return files


@pytest.mark.parametrize("patient_file", _patient_files())
def test_patient_runs_full_pipeline(protocol_id, patient_file):
    patient = json.loads(patient_file.read_text())
    patient_id = patient["patient_id"]

    with open(patient_file, "rb") as f:
        ingest_resp = client.post(
            "/ingest/patient",
            files={"file": (patient_file.name, f, "application/json")},
        )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["patient_id"] == patient_id

    audit_resp = client.post(
        "/audit/generate",
        params={"patient_id": patient_id, "protocol_id": protocol_id},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    result = audit_resp.json()

    assert result["decision"] in ("ELIGIBLE", "INELIGIBLE", "REQUIRES_HUMAN_REVIEW")
    assert 0.0 <= result["confidence"] <= 1.0

    assert Path(result["json_path"]).exists()
    assert Path(result["pdf_path"]).exists()
    assert Path(result["pdf_path"]).stat().st_size > 0

    dossier_id = result["dossier_id"]
    get_resp = client.get(f"/audit/{dossier_id}")
    assert get_resp.status_code == 200

    pdf_resp = client.get(f"/audit/pdf/{dossier_id}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"

    dossier_text = json.dumps(get_resp.json())
    assert patient.get("email", "zzz-none") not in dossier_text
    assert patient.get("mrn", "zzz-none") not in dossier_text
