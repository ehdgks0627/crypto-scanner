import { useParams } from "react-router-dom";

import { SnapshotDiffView } from "../features/snapshots/SnapshotViews";

export function SnapshotDiffPage() {
  return <SnapshotDiffView id={Number(useParams().id)} />;
}
