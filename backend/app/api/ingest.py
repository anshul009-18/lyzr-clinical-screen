import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.app.services.ingestion_service import (
    extract_protocol_text,
    parse_patient_file,
)
from backend.app.db import storage

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/protocol")
async def ingest_protocol(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Protocol must be uploaded as a PDF")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        text = extract_protocol_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(422, "No extractable text found in PDF — may be a scanned image (OCR fallback not yet implemented)")

    storage.save_protocol(protocol_id=file.filename, raw_text=text)

    return {"protocol_id": file.filename, "extracted_text": text, "char_count": len(text)}


@router.get("/protocol/{protocol_id}")
async def get_protocol(protocol_id: str):
    result = storage.get_protocol(protocol_id)
    if not result:
        raise HTTPException(404, "Protocol not found")
    return result


@router.post("/patient")
async def ingest_patient(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix
    original_stem = Path(file.filename).stem  # ← real name, not temp name

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        patient = parse_patient_file(tmp_path, fallback_id=original_stem)
    except (ValueError, NotImplementedError) as e:
        raise HTTPException(422, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    storage.save_patient(patient.patient_id, patient.model_dump())
    return patient


@router.get("/patient/{patient_id}")
async def get_patient(patient_id: str):
    result = storage.get_patient(patient_id)
    if not result:
        raise HTTPException(404, "Patient not found")
    return result


@router.get("/patients")
async def list_all_patients():
    return {"patient_ids": storage.list_patients()}
