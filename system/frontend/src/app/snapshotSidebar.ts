export type SnapshotSidebarSection = "snapshot" | "migration" | "risk" | null;

export interface SnapshotSidebarState {
  snapshotPath: string;
  migrationPath: string;
  riskPath: string;
  activeSection: SnapshotSidebarSection;
}

export function getSnapshotSidebarState(pathname: string): SnapshotSidebarState {
  const [pathOnly] = pathname.split(/[?#]/);
  const segments = pathOnly.split("/").filter(Boolean);
  const isSnapshotRoute = segments[0] === "snapshots";
  const snapshotId = isSnapshotRoute ? segments[1] : undefined;
  const snapshotPath = snapshotId ? `/snapshots/${snapshotId}` : "/snapshots";

  let activeSection: SnapshotSidebarSection = null;
  if (isSnapshotRoute) {
    if (segments[2] === "migration") {
      activeSection = "migration";
    } else if (segments[2] === "risk") {
      activeSection = "risk";
    } else {
      activeSection = "snapshot";
    }
  }

  return {
    snapshotPath,
    migrationPath: snapshotId ? `${snapshotPath}/migration` : "/snapshots",
    riskPath: snapshotId ? `${snapshotPath}/risk` : "/snapshots",
    activeSection
  };
}
