"""
Shared pipeline state object — passed between every agent in the
Lyzr triad (Environment / Agent / Inference). Every agent reads
from and writes to this object so the full pipeline stays traceable
end to end, and so the Regulatory Audit Agent (Phase 4) has a single
source of truth to build the dossier from.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PHIStatus(str, Enum):
    UNSCRUBBED = "unscrubbed"
    SCRUBBED = "scrubbed"
    SCRUB_FAILED = "scrub_failed"


class ScreeningDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"
    PENDING = "PENDING"


class CriterionRule(BaseModel):
    field: str
    operator: str  # >, <, >=, <=, ==, in, not_in
    value: float | str | list
    unit: Optional[str] = None
    source_citation: Optional[str] = None  # protocol section/page


class ExtractedCriteria(BaseModel):
    inclusion: list[CriterionRule] = Field(default_factory=list)
    exclusion: list[CriterionRule] = Field(default_factory=list)
    washout_days: Optional[int] = None


class CriterionEvaluation(BaseModel):
    rule: CriterionRule
    patient_value: float | str | None
    passed: bool
    confidence: float  # 0.0 - 1.0
    notes: Optional[str] = None


class ScreeningResult(BaseModel):
    decision: ScreeningDecision = ScreeningDecision.PENDING
    confidence: float = 0.0
    evaluations: list[CriterionEvaluation] = Field(default_factory=list)
    flagged_by_medical_safety: bool = False
    flag_reason: Optional[str] = None


class AuditEvent(BaseModel):
    step: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detail: str


class PipelineState(BaseModel):
    """
    One instance of this object represents a single patient x protocol
    run through the full pipeline (Phases 1-4).
    """

    patient_id: str
    protocol_id: str

    # Phase 1 — Ingestion
    raw_protocol_text: Optional[str] = None
    raw_patient_record: Optional[dict] = None

    # Phase 2 — Protocol Criteria Agent
    extracted_criteria: Optional[ExtractedCriteria] = None

    # Phase 3 — PHI Scrubbing
    phi_status: PHIStatus = PHIStatus.UNSCRUBBED
    scrubbed_patient_record: Optional[dict] = None

    # Phase 4 — Screening / Medical Safety
    screening_result: ScreeningResult = Field(default_factory=ScreeningResult)

    # Phase 4 — Regulatory Audit
    audit_dossier_path: Optional[str] = None

    # Traceability (streamed to Lyzr AIMS)
    events: list[AuditEvent] = Field(default_factory=list)

    def log_event(self, step: str, detail: str) -> None:
        self.events.append(AuditEvent(step=step, detail=detail))
