import { describe, expect, it } from "vitest";

import { getSnapshotSidebarState } from "./snapshotSidebar";

describe("snapshot sidebar state", () => {
  it.each([
    [
      "/snapshots",
      {
        activeSection: "snapshot",
        snapshotPath: "/snapshots",
        migrationPath: "/snapshots",
        riskPath: "/snapshots",
        performancePath: "/snapshots"
      }
    ],
    [
      "/snapshots/7",
      {
        activeSection: "snapshot",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk",
        performancePath: "/snapshots/7/performance"
      }
    ],
    [
      "/snapshots/7/risk",
      {
        activeSection: "risk",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk",
        performancePath: "/snapshots/7/performance"
      }
    ],
    [
      "/snapshots/7/migration",
      {
        activeSection: "migration",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk",
        performancePath: "/snapshots/7/performance"
      }
    ],
    [
      "/snapshots/7/performance",
      {
        activeSection: "performance",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk",
        performancePath: "/snapshots/7/performance"
      }
    ],
    [
      "/targets",
      {
        activeSection: null,
        snapshotPath: "/snapshots",
        migrationPath: "/snapshots",
        riskPath: "/snapshots",
        performancePath: "/snapshots"
      }
    ]
  ])("returns the expected sidebar state for %s", (pathname, expected) => {
    expect(getSnapshotSidebarState(pathname)).toEqual(expected);
  });
});
