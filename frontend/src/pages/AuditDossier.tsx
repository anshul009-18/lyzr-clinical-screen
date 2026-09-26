import { useEffect, useState } from "react";
import { getDossier, dossierPdfUrl, ApiError } from "../api/client";
import type { AuditDossier } from "../types";

interface AuditDossierPageProps {
  dossierId: string;
  onBack: () => void;
}

export default function AuditDossierPage({ dossierId, onBack }: AuditDossierPageProps) {
  const [dossier, setDossier] = useState<AuditDossier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frameFailed, setFrameFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getDossier(dossierId)
      .then((d) => !cancelled && setDossier(d))
      .catch((e) =>
        !cancelled &&
        setError(e instanceof ApiError ? e.message : "Could not load dossier")
      );
    return () => {
      cancelled = true;
    };
  }, [dossierId]);

  return (
    <div>
      <a className="back-link" href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>
        ← Start a new screening
      </a>
      <h2 className="page-title">Audit dossier</h2>
      <p className="page-sub">
        FDA-style eligibility dossier — every criterion cited to its protocol
        section. No patient identifiers appear anywhere in this record.
      </p>

      {error && <div className="error-box">{error}</div>}

      {dossier && (
        <>
          <dl className="meta-row">
            <div>
              <dt>Dossier ID</dt>
              <dd>{dossier.dossier_id}</dd>
            </div>
            <div>
              <dt>Generated</dt>
              <dd>{new Date(dossier.generated_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt>Patient reference</dt>
              <dd>{dossier.patient_id}</dd>
            </div>
            <div>
              <dt>Protocol</dt>
              <dd>{dossier.protocol_id}</dd>
            </div>
          </dl>

          <div className="pdf-card">
            <div className="pdf-toolbar">
              <span className="pdf-toolbar-label">Preview</span>

              <a
                className="pdf-toolbar-link"
                href={dossierPdfUrl(dossier.dossier_id)}
                target="_blank"
                rel="noreferrer"
              >
                Open in new tab ↗
              </a>
            </div>

            {!frameFailed ? (
              <iframe
                className="pdf-frame"
                src={dossierPdfUrl(dossier.dossier_id)}
                title={`Audit dossier ${dossier.dossier_id}`}
                onError={() => setFrameFailed(true)}
              />
            ) : (
              <div className="pdf-frame pdf-frame-fallback">
                <p>
                  Preview didn't load — a browser extension or privacy
                  setting may be blocking embedded PDFs.
                </p>

                <a
                  className="secondary-button"
                  href={dossierPdfUrl(dossier.dossier_id)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open PDF in a new tab
                </a>
              </div>
            )}
          </div>

          <div className="action-row">
            <a
              className="primary-button"
              style={{ textDecoration: "none", display: "inline-block" }}
              href={dossierPdfUrl(dossier.dossier_id)}
              download={`${dossier.dossier_id}.pdf`}
            >
              Download PDF
            </a>

            <a
              className="secondary-button"
              style={{ textDecoration: "none", display: "inline-block" }}
              href={`/audit/${dossier.dossier_id}`}
              download={`${dossier.dossier_id}.json`}
            >
              Download JSON
            </a>
          </div>
        </>
      )}
    </div>
  );
}
