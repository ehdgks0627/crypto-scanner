import { useParams } from "react-router-dom";

import { DiscoveryDetailView } from "../features/discoveries/DiscoveryViews";

export function DiscoveryDetailPage() {
  return <DiscoveryDetailView id={Number(useParams().id)} />;
}
