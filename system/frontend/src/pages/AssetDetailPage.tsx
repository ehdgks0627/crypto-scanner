import { useParams } from "react-router-dom";

import { AssetDetailView } from "../features/snapshots/SnapshotViews";

export function AssetDetailPage() {
  const params = useParams();
  return <AssetDetailView snapshotId={Number(params.id)} assetId={Number(params.aid)} />;
}
