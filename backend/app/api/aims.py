from fastapi import APIRouter

from backend.app.services.aims_stream import get_local_event_log

router = APIRouter(prefix="/aims", tags=["aims"])


@router.get("/events")
async def list_aims_events(patient_id: str | None = None, limit: int = 200):
    """
    Read-only feed for the dashboard. Backed by the same local event
    log aims_stream.stream_event() populates — every entry already
    passed the PHI re-scan gate before being added there, so nothing
    extra is needed here to make this safe to expose.
    """
    events = get_local_event_log()
    if patient_id:
        events = [e for e in events if e["patient_id"] == patient_id]
    return {"events": events[-limit:], "total": len(events)}
