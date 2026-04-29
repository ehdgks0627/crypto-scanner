import { useParams } from "react-router-dom";

import { RiskAssessmentView } from "../features/risk/RiskViews";

export function SnapshotRiskPage() {
  return <RiskAssessmentView snapshotId={Number(useParams().id)} />;
}
