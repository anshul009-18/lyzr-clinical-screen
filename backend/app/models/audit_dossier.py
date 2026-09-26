from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from agents.orchestration.state import ScreeningDecision, AuditEvent


class DossierCriterionLine(BaseModel):
    field: str
    category: str  # "inclusion" | "exclusion" | "washout"
    operator: str
    threshold: float | str | list
    unit: Optional[str] = None
    source_citation: Optional[str] = None
    patient_value: float | str | None
    result: str  # "MET" | "NOT MET" | "UNRESOLVED"
    confidence: float


class AuditDossier(BaseModel):
    dossier_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    patient_id: str
    protocol_id: str
    screening_decision: ScreeningDecision
    overall_confidence: float
    flagged_by_medical_safety: bool
    medical_safety_reason: Optional[str] = None
    criteria_lines: list[DossierCriterionLine]
    event_trail: list[AuditEvent]
    compliance_statement: str
