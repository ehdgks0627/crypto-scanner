import { useParams } from "react-router-dom";

import { JobDetailView } from "../features/jobs/JobViews";

export function ScanDetailPage() {
  return <JobDetailView id={Number(useParams().id)} />;
}
