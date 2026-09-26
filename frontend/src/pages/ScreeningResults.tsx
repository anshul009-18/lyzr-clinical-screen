import { useEffect, useState } from "react";
import { generateAudit, getDossier, ApiError } from "../api/client";
import type { AuditDossier, GenerateAuditResponse } from "../types";

interface ScreeningResultsProps {
  patientId: string;
  protocolId: string;
  onBack: () => void;
  onDossierGenerated: (res: GenerateAuditResponse) => void;
}

const DECISION_LABEL: Record<string, string> = {
  ELIGIBLE: "Eligible",
  INELIGIBLE: "Not eligible",
  REQUIRES_HUMAN_REVIEW: "Needs human review",
  PENDING: "Pending",
};

const DECISION_CLASS: Record<string, string> = {
  ELIGIBLE: "eligible",
  INELIGIBLE: "ineligible",
  REQUIRES_HUMAN_REVIEW: "review",
  PENDING: "review",
};

const RESULT_CLASS: Record<string, string> = {
  MET: "met",
  "NOT MET": "not-met",
  UNRESOLVED: "unresolved",
};

export default function ScreeningResults({
  patientId,
  protocolId,
  onBack,
  onDossierGenerated,
}: ScreeningResultsProps) {
  const [dossier, setDossier] = useState<AuditDossier | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateAuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);
      try {
        const genRes = await generateAudit(patientId, protocolId);
        if (cancelled) return;
        setGenerateResult(genRes);

        const full = await getDossier(genRes.dossier_id);
        if (cancelled) return;
        setDossier(full);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError
              ? e.message
              : "Screening could not be completed — check that PHI scrubbing and criteria extraction both succeeded."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [patientId, protocolId]);

  return (
    <div>
      <a className="back-link" href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>
        ← Start a new screening
      </a>
      <h2 className="page-title">Screening result</h2>

      <dl className="meta-row">
        <div>
          <dt>Patient reference</dt>
          <dd>{patientId}</dd>
        </div>
        <div>
          <dt>Protocol</dt>
          <dd>{protocolId}</dd>
        </div>
      </dl>

      {loading && <div className="empty-state">Running PHI scrub, screening, and medical safety checks…</div>}

      {error && <div className="error-box">{error}</div>}

      {dossier && (
        <>
          <div className={`status-banner ${DECISION_CLASS[dossier.screening_decision]}`}>
            <p className="decision">{DECISION_LABEL[dossier.screening_decision]}</p>
            <p className="confidence">
              confidence: {dossier.overall_confidence.toFixed(2)}
            </p>
          </div>

          {dossier.flagged_by_medical_safety && (
            <div className="safety-flag">
              <strong>Flagged by medical safety review</strong>
              {dossier.medical_safety_reason}
            </div>
          )}

          <table className="criteria-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Category</th>
                <th>Requirement</th>
                <th>Patient value</th>
                <th>Result</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {dossier.criteria_lines.map((line, i) => (
                <tr key={i}>
                  <td className="field">{line.field}</td>
                  <td>{line.category}</td>
                  <td>
                    {line.operator} {line.threshold} {line.unit}
                  </td>
                  <td>{line.patient_value ?? "Not recorded"}</td>
                  <td>
                    <span className={`result-pill ${RESULT_CLASS[line.result]}`}>
                      {line.result}
                    </span>
                  </td>
                  <td className="citation">{line.source_citation}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button
            className="primary-button"
            onClick={() => generateResult && onDossierGenerated(generateResult)}
          >
            View audit dossier
          </button>
        </>
      )}
    </div>
  );
}
