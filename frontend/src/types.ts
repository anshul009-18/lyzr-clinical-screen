export type ScreeningDecision =
  | "ELIGIBLE"
  | "INELIGIBLE"
  | "REQUIRES_HUMAN_REVIEW"
  | "PENDING";

export interface CriteriaLine {
  field: string;
  category: "inclusion" | "exclusion";
  operator: string;
  threshold: number | string;
  unit: string;
  source_citation: string;
  patient_value: number | string | null;
  result: "MET" | "NOT MET" | "UNRESOLVED";
  confidence: number;
}

export interface AuditDossier {
  dossier_id: string;
  generated_at: string;
  patient_id: string;
  protocol_id: string;
  screening_decision: ScreeningDecision;
  overall_confidence: number;
  flagged_by_medical_safety: boolean;
  medical_safety_reason: string | null;
  criteria_lines: CriteriaLine[];
}

export interface GenerateAuditResponse {
  dossier_id: string;
  decision: ScreeningDecision;
  confidence: number;
  json_path: string;
  pdf_path: string;
}

export interface IngestProtocolResponse {
  protocol_id: string;
  char_count: number;
}

export interface IngestPatientResponse {
  patient_id: string;
  [key: string]: unknown;
}

export interface AimsEvent {
  patient_id: string;
  step: string;
  detail: string;
}
