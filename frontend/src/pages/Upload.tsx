import { useCallback, useId, useState } from "react";
import { ingestProtocol, ingestPatient, ApiError } from "../api/client";

interface UploadProps {
  onReady: (patientId: string, protocolId: string) => void;
}

type FieldStatus = "empty" | "uploading" | "ready" | "error";

interface DropzoneProps {
  stepIndex: number;
  stepLabel: string;
  title: string;
  description: string;
  formatLabel: string;
  accept: string;
  file: File | null;
  onFile: (file: File) => void;
  status: FieldStatus;
  readyLabel: string | null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function DocumentIcon() {
  return (
    <svg
      className="dropzone-icon"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M9 13h6" />
      <path d="M9 17h6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      className="check-icon"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

function Dropzone({
  stepIndex,
  stepLabel,
  title,
  description,
  formatLabel,
  accept,
  file,
  onFile,
  status,
  readyLabel,
}: DropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputId = useId();
  const descriptionId = useId();

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      const dropped = e.dataTransfer.files?.[0];
      if (dropped) onFile(dropped);
    },
    [onFile]
  );

  const isFilled = status === "ready" || status === "uploading";

  return (
    <div className="upload-card">
      <div className="upload-card-header">
        <span className="step-label">
          Step {stepIndex} — {stepLabel}
        </span>
        <h3 className="upload-card-title">{title}</h3>
        <p className="upload-card-description" id={descriptionId}>
          {description}
        </p>
        <span className="format-tag">{formatLabel}</span>
      </div>

      <div
        className={[
          "dropzone",
          isDragOver ? "is-dragover" : "",
          isFilled ? "is-filled" : "",
          status === "error" ? "is-error" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
      >
        {!isFilled && (
          <div className="dropzone-empty">
            <span className="dropzone-icon-wrap">
              <DocumentIcon />
            </span>
            {status === "error" ? (
              <p className="dropzone-error-text">Upload failed — try again</p>
            ) : (
              <p className="dropzone-primary-text">Drag and drop your file here</p>
            )}
            <p className="dropzone-secondary-text">or choose a file from your computer</p>
          </div>
        )}

        {isFilled && (
          <div className="dropzone-filled">
            <span className={`file-status-icon ${status === "uploading" ? "is-pending" : "is-ready"}`}>
              {status === "uploading" ? <Spinner /> : <CheckIcon />}
            </span>
            <div className="file-details">
              <span className="file-name">{file?.name}</span>
              <span className="file-meta">
                {file ? formatFileSize(file.size) : ""}
                {file && readyLabel ? " · " : ""}
                {status === "uploading" ? "Uploading…" : readyLabel ?? "Ready for screening"}
              </span>
            </div>
          </div>
        )}

        <label className="file-input-label" htmlFor={inputId}>
          {isFilled ? "Replace file" : "Choose file"}
          <input
            id={inputId}
            type="file"
            accept={accept}
            className="visually-hidden-input"
            aria-describedby={descriptionId}
            onChange={(e) => {
              const selected = e.target.files?.[0];
              if (selected) onFile(selected);
            }}
          />
        </label>
      </div>
    </div>
  );
}

export default function Upload({ onReady }: UploadProps) {
  const [protocolFile, setProtocolFile] = useState<File | null>(null);
  const [patientFile, setPatientFile] = useState<File | null>(null);
  const [protocolId, setProtocolId] = useState<string | null>(null);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [uploadingProtocol, setUploadingProtocol] = useState(false);
  const [uploadingPatient, setUploadingPatient] = useState(false);
  const [protocolError, setProtocolError] = useState(false);
  const [patientError, setPatientError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runningScreen, setRunningScreen] = useState(false);

  async function handleProtocolFile(file: File) {
    setProtocolFile(file);
    setProtocolId(null);
    setError(null);
    setProtocolError(false);
    setUploadingProtocol(true);
    try {
      const res = await ingestProtocol(file);
      setProtocolId(res.protocol_id);
    } catch (e) {
      setProtocolError(true);
      setError(e instanceof ApiError ? e.message : "Could not ingest protocol");
    } finally {
      setUploadingProtocol(false);
    }
  }

  async function handlePatientFile(file: File) {
    setPatientFile(file);
    setPatientId(null);
    setError(null);
    setPatientError(false);
    setUploadingPatient(true);
    try {
      const res = await ingestPatient(file);
      setPatientId(res.patient_id);
    } catch (e) {
      setPatientError(true);
      setError(e instanceof ApiError ? e.message : "Could not ingest patient record");
    } finally {
      setUploadingPatient(false);
    }
  }

  async function handleRunScreening() {
    if (!protocolFile || !protocolId || !patientId) return;
    setError(null);
    setRunningScreen(true);
    try {
      // Ensures criteria are extracted for this protocol before the
      // Results page tries to display a decision against it.
      const { extractCriteria } = await import("../api/client");
      await extractCriteria(protocolFile);
      onReady(patientId, protocolId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not extract eligibility criteria");
    } finally {
      setRunningScreen(false);
    }
  }

  const canRun = Boolean(protocolId && patientId && !runningScreen);

  function protocolStatus(): FieldStatus {
    if (protocolError) return "error";
    if (uploadingProtocol) return "uploading";
    if (protocolId) return "ready";
    return "empty";
  }

  function patientStatus(): FieldStatus {
    if (patientError) return "error";
    if (uploadingPatient) return "uploading";
    if (patientId) return "ready";
    return "empty";
  }

  const step1Complete = Boolean(protocolId);
  const step2Complete = Boolean(patientId);
  const step2Active = step1Complete && !step2Complete;
  const step3Active = step1Complete && step2Complete;

  function stepClass(complete: boolean, active: boolean) {
    if (complete) return "stepper-item is-complete";
    if (active) return "stepper-item is-active";
    return "stepper-item is-upcoming";
  }

  return (
    <div className="upload-page">
      <header className="page-intro">
        <h2 className="page-title">Screen a patient</h2>
        <p className="page-sub">
          Upload a clinical trial protocol and a de-identified patient record to evaluate eligibility.
        </p>
        <ul className="trust-badges" aria-label="Screening safeguards">
          <li className="trust-badge">
            <CheckIcon /> PHI protected before inference
          </li>
          <li className="trust-badge">
            <CheckIcon /> Deterministic rule evaluation
          </li>
          <li className="trust-badge">
            <CheckIcon /> FDA-style audit trail
          </li>
        </ul>
      </header>

      <ol className="stepper" aria-label="Screening workflow progress">
        <li className={stepClass(step1Complete, !step1Complete)}>
          <span className="stepper-index">{step1Complete ? <CheckIcon /> : 1}</span>
          <span className="stepper-name">Protocol</span>
        </li>
        <li className="stepper-connector" aria-hidden="true" />
        <li className={stepClass(step2Complete, step2Active)}>
          <span className="stepper-index">{step2Complete ? <CheckIcon /> : 2}</span>
          <span className="stepper-name">Patient</span>
        </li>
        <li className="stepper-connector" aria-hidden="true" />
        <li className={stepClass(false, step3Active)}>
          <span className="stepper-index">3</span>
          <span className="stepper-name">Screening</span>
        </li>
      </ol>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <div className="upload-grid">
        <Dropzone
          stepIndex={1}
          stepLabel="Protocol"
          title="Trial protocol"
          description="Upload the clinical trial protocol used to determine eligibility."
          formatLabel="PDF"
          accept="application/pdf"
          file={protocolFile}
          onFile={handleProtocolFile}
          status={protocolStatus()}
          readyLabel={protocolId ? `Ingested as ${protocolId}` : null}
        />
        <Dropzone
          stepIndex={2}
          stepLabel="Patient"
          title="Patient record"
          description="Upload a de-identified patient record for screening."
          formatLabel="JSON, TXT, PDF"
          accept=".json,.txt,.pdf"
          file={patientFile}
          onFile={handlePatientFile}
          status={patientStatus()}
          readyLabel={patientId ? `Ingested as ${patientId}` : null}
        />
      </div>

      <div className="run-row">
        <button
          className="primary-button run-button"
          disabled={!canRun}
          onClick={handleRunScreening}
        >
          {runningScreen ? (
            <>
              <Spinner /> Screening…
            </>
          ) : (
            <>Run screening →</>
          )}
        </button>
      </div>

      <footer className="security-footer">
        <p className="security-footer-title">Secure clinical screening</p>
        <p className="security-footer-sub">
          De-identified patient data · Deterministic evaluation · Auditable workflow
        </p>
      </footer>
    </div>
  );
}
