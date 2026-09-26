from fastapi import APIRouter, HTTPException

from backend.app.db import storage

router = APIRouter(prefix="/hitl", tags=["hitl"])


@router.get("/pending")
async def list_pending():
    return {"pending": storage.list_pending_hitl_reviews()}


@router.get("/{dossier_id}")
async def get_review(dossier_id: str):
    review = storage.get_hitl_review(dossier_id)
    if not review:
        raise HTTPException(404, "No HITL review record for this dossier")
    return review


@router.post("/{dossier_id}/resolve")
async def resolve_review(dossier_id: str, status: str, resolved_by: str = "reviewer"):
    if status not in ("approved", "rejected"):
        raise HTTPException(400, "status must be 'approved' or 'rejected'")
    updated = storage.resolve_hitl_review(dossier_id, status, resolved_by)
    if not updated:
        raise HTTPException(404, "No pending HITL review found for this dossier")
    return {"dossier_id": dossier_id, "status": status, "resolved_by": resolved_by}
