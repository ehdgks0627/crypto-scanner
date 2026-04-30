import { useParams } from "react-router-dom";

import { PerformanceEvaluationView } from "../features/performance/PerformanceViews";

export function SnapshotPerformancePage() {
  return <PerformanceEvaluationView snapshotId={Number(useParams().id)} />;
}
