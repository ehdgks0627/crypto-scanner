import { useParams } from "react-router-dom";

import { SnapshotDetailView } from "../features/snapshots/SnapshotViews";

export function SnapshotDetailPage() {
  return <SnapshotDetailView id={Number(useParams().id)} />;
}
