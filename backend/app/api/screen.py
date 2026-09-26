import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.app.services.ingestion_service import extract_protocol_text
from backend.app.services.lyzr_client import extract_protocol_criteria, LyzrAgentError
from backend.app.models.criteria import ExtractedCriteria
from backend.app.db import storage

router = APIRouter(prefix="/screen", tags=["screening"])


@router.post("/extract-criteria")
async def extract_criteria(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Protocol must be uploaded as a PDF")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        protocol_text = extract_protocol_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not protocol_text.strip():
        raise HTTPException(422, "No extractable text found in PDF")

    try:
        raw_criteria = extract_protocol_criteria(protocol_text, protocol_id=file.filename)
    except LyzrAgentError as e:
        raise HTTPException(502, f"Criteria extraction failed: {e}")

    try:
        criteria = ExtractedCriteria(**raw_criteria)
    except Exception as e:
        raise HTTPException(502, f"Agent returned criteria in unexpected shape: {e}")

    storage.save_protocol(protocol_id=file.filename, raw_text=protocol_text, criteria=criteria.model_dump())

    return {
        "protocol_id": file.filename,
        "criteria": criteria,
        "rule_count": len(criteria.inclusion) + len(criteria.exclusion),
    }


@router.get("/criteria/{protocol_id}")
async def get_criteria(protocol_id: str):
    result = storage.get_protocol(protocol_id)
    if not result or not result.get("criteria"):
        raise HTTPException(404, "No extracted criteria found for this protocol")
    return result["criteria"]
