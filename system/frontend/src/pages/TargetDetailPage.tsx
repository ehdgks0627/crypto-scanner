import { useParams } from "react-router-dom";

import { TargetDetailView } from "../features/targets/TargetDetailView";

export function TargetDetailPage() {
  const id = Number(useParams().id);
  return <TargetDetailView id={id} />;
}
