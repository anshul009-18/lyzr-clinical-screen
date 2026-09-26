import { useState } from "react";
import Upload from "./pages/Upload";
import ScreeningResults from "./pages/ScreeningResults";
import AuditDossierPage from "./pages/AuditDossier";
import AimsDashboard from "./pages/AimsDashboard";
import type { GenerateAuditResponse } from "./types";

type Route =
  | { name: "upload" }
  | { name: "results"; patientId: string; protocolId: string }
  | { name: "dossier"; dossierId: string }
  | { name: "aims" };

export default function App() {
  const [route, setRoute] = useState<Route>({ name: "upload" });

  return (
    <div className="shell">
      <div className="topbar">
        <div className="brand">
          <h1>lyzr-clinical-screen</h1>
          <span className="service-tag">Governed Trial Screening</span>
        </div>
        <button className="topbar-button" onClick={() => setRoute({ name: "aims" })}>
          AIMS Trail
        </button>
      </div>

      {route.name === "upload" && (
        <Upload
          onReady={(patientId, protocolId) =>
            setRoute({ name: "results", patientId, protocolId })
          }
        />
      )}

      {route.name === "results" && (
        <ScreeningResults
          patientId={route.patientId}
          protocolId={route.protocolId}
          onBack={() => setRoute({ name: "upload" })}
          onDossierGenerated={(res: GenerateAuditResponse) =>
            setRoute({ name: "dossier", dossierId: res.dossier_id })
          }
        />
      )}

      {route.name === "dossier" && (
        <AuditDossierPage
          dossierId={route.dossierId}
          onBack={() => setRoute({ name: "upload" })}
        />
      )}

      {route.name === "aims" && (
        <AimsDashboard onBack={() => setRoute({ name: "upload" })} />
      )}
    </div>
  );
}
