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
        riskPath: "/snapshots"
      }
    ],
    [
      "/snapshots/7",
      {
        activeSection: "snapshot",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk"
      }
    ],
    [
      "/snapshots/7/risk",
      {
        activeSection: "risk",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk"
      }
    ],
    [
      "/snapshots/7/migration",
      {
        activeSection: "migration",
        snapshotPath: "/snapshots/7",
        migrationPath: "/snapshots/7/migration",
        riskPath: "/snapshots/7/risk"
      }
    ],
    [
      "/targets",
      {
        activeSection: null,
        snapshotPath: "/snapshots",
        migrationPath: "/snapshots",
        riskPath: "/snapshots"
      }
    ]
  ])("returns the expected sidebar state for %s", (pathname, expected) => {
    expect(getSnapshotSidebarState(pathname)).toEqual(expected);
  });
});
