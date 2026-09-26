import type {
  AuditDossier,
  GenerateAuditResponse,
  IngestPatientResponse,
  IngestProtocolResponse,
} from "../types";

/**
 * All requests go through the Vite dev-server proxy (see vite.config.ts)
 * so this stays a relative path — no CORS config needed in dev, and in
 * production this should be served behind the same origin as the API
 * (or replace with an absolute API base URL via an env var).
 */

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function ingestProtocol(file: File): Promise<IngestProtocolResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<IngestProtocolResponse>("/ingest/protocol", {
    method: "POST",
    body: form,
  });
}

export async function ingestPatient(file: File): Promise<IngestPatientResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<IngestPatientResponse>("/ingest/patient", {
    method: "POST",
    body: form,
  });
}

export async function extractCriteria(protocolFile: File) {
  const form = new FormData();
  form.append("file", protocolFile);
  return request<{ protocol_id: string; criteria: unknown; rule_count: number }>(
    "/screen/extract-criteria",
    { method: "POST", body: form }
  );
}

export async function generateAudit(
  patientId: string,
  protocolId: string
): Promise<GenerateAuditResponse> {
  const params = new URLSearchParams({ patient_id: patientId, protocol_id: protocolId });
  return request<GenerateAuditResponse>(`/audit/generate?${params.toString()}`, {
    method: "POST",
  });
}

export async function getDossier(dossierId: string): Promise<AuditDossier> {
  return request<AuditDossier>(`/audit/${dossierId}`);
}

export function dossierPdfUrl(dossierId: string): string {
  // Served as a static file by the backend — see README for the
  // FastAPI StaticFiles mount this expects at /audit/pdf/{dossier_id}.
  return `/audit/pdf/${dossierId}`;
}

export { ApiError };

import type { AimsEvent } from "../types";

export async function getAimsEvents(limit = 200): Promise<{ events: AimsEvent[]; total: number }> {
  return request(`/aims/events?limit=${limit}`);
}
