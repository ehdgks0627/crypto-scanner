import { useParams } from "react-router-dom";

import { MigrationPlanView } from "../features/migration/MigrationViews";

export function SnapshotMigrationPage() {
  return <MigrationPlanView snapshotId={Number(useParams().id)} />;
}
