import { useEffect, useState } from "react";
import { getAimsEvents } from "../api/client";
import type { AimsEvent } from "../types";

const STEP_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  criteria_extraction: "Protocol Criteria Extracted",
  phi_scrub: "PHI Scrubbed",
  screening: "Screening Decision",
  medical_safety: "Medical Safety Check",
  redaction_verification: "Redaction Verified",
};

export default function AimsDashboard({ onBack }: { onBack: () => void }) {
  const [events, setEvents] = useState<AimsEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await getAimsEvents();
        if (!cancelled) {
          setEvents(res.events.slice().reverse()); // newest first
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }

    poll();
    const interval = setInterval(poll, 5000); // live: refresh every 5s
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="aims-dashboard">
      <button onClick={onBack}>&larr; Back</button>
      <h2>AIMS Event Trail</h2>
      <p className="service-tag">
        Live pipeline trace — every ingestion, scrub, screening, and audit step, per
        patient. Refreshes every 5 seconds. Identical to what would stream to Lyzr
        AIMS in production.
      </p>

      {error && <p style={{ color: "#a11616" }}>Failed to load events: {error}</p>}

      <table>
        <thead>
          <tr>
            <th>Patient</th>
            <th>Step</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={i}>
              <td>{e.patient_id}</td>
              <td>{STEP_LABELS[e.step] ?? e.step}</td>
              <td>{e.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {events.length === 0 && !error && <p>No events yet — run a patient through the pipeline first.</p>}
    </div>
  );
}
