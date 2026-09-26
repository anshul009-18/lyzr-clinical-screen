import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from agents.orchestration.state import PipelineState, ExtractedCriteria
from agents.orchestration.pipeline import (
    run_phi_scrub, run_screening, run_medical_safety,
    verify_before_persist, PHIGateError,
)
from agents.regulatory_audit_agent.dossier_template import build_dossier, render_pdf
from backend.app.db import storage
from backend.app.services.aims_stream import stream_event, AIMSStreamError
from backend.app.services.hitl_webhook import should_pause_for_review, trigger_hitl_pause, HITLWebhookError

router = APIRouter(prefix="/audit", tags=["audit"])

DOSSIER_DIR = Path(__file__).resolve().parents[3] / "data" / "audit_dossiers"
DOSSIER_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/generate")
async def generate_audit(patient_id: str, protocol_id: str):
    patient_record = storage.get_patient(patient_id)
    if patient_record is None:
        raise HTTPException(404, f"No ingested patient record for patient_id={patient_id}")

    protocol = storage.get_protocol(protocol_id)
    if protocol is None or not protocol.get("criteria"):
        raise HTTPException(404, f"No extracted criteria for protocol_id={protocol_id}")

    state = PipelineState(patient_id=patient_id, protocol_id=protocol_id)
    state.raw_patient_record = patient_record
    state.extracted_criteria = ExtractedCriteria(**protocol["criteria"])

    try:
        run_phi_scrub(state)
        run_screening(state)
        run_medical_safety(state)
    except PHIGateError as e:
        raise HTTPException(422, f"Pipeline blocked before dossier could be generated: {e}")

    dossier = build_dossier(state)

    try:
        for event in state.events:
            stream_event(state.patient_id, event.step, event.detail)
        verify_before_persist(dossier.model_dump(), "audit_dossier_json", state)
    except (AIMSStreamError, PHIGateError) as e:
        raise HTTPException(500, f"Refused to persist/stream dossier — PHI check failed: {e}")

    json_path = DOSSIER_DIR / f"{dossier.dossier_id}.json"
    json_path.write_text(dossier.model_dump_json(indent=2))

    pdf_path = DOSSIER_DIR / f"{dossier.dossier_id}.pdf"
    render_pdf(dossier, str(pdf_path))
    state.audit_dossier_path = str(pdf_path)
    hitl_pending = should_pause_for_review(dossier.screening_decision.value, dossier.overall_confidence)
    if hitl_pending:
        storage.save_hitl_review(
            dossier_id=dossier.dossier_id, patient_id=patient_id, protocol_id=protocol_id,
            decision=dossier.screening_decision.value, confidence=dossier.overall_confidence,
            reason=dossier.medical_safety_reason or f"Confidence {dossier.overall_confidence:.2f} below threshold",
        )
        try:
            trigger_hitl_pause(
                dossier_id=dossier.dossier_id, patient_id=patient_id, protocol_id=protocol_id,
                decision=dossier.screening_decision.value, confidence=dossier.overall_confidence,
                reason=dossier.medical_safety_reason,
            )
        except HITLWebhookError:
            pass  # still recorded in storage above — webhook delivery is best-effort, the pause itself is not

    return {
        "dossier_id": dossier.dossier_id,
        "decision": dossier.screening_decision,
        "confidence": dossier.overall_confidence,
        "json_path": str(json_path),
        "pdf_path": str(pdf_path),
        "hitl_pending": hitl_pending,
    }


@router.get("/{dossier_id}")
async def get_audit(dossier_id: str):
    json_path = DOSSIER_DIR / f"{dossier_id}.json"
    if not json_path.exists():
        raise HTTPException(404, "Dossier not found")
    return json.loads(json_path.read_text())


@router.get("/pdf/{dossier_id}")
async def get_dossier_pdf(dossier_id: str):
    """
    Serves the raw PDF file for the frontend's preview iframe and
    download button. content_disposition_type="inline" is required —
    FileResponse defaults to "attachment" whenever filename is set,
    which blocks browsers from rendering it inside an <iframe> and
    silently shows a blank box instead.
    """
    pdf_path = DOSSIER_DIR / f"{dossier_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Dossier PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{dossier_id}.pdf",
        content_disposition_type="inline",
    )
