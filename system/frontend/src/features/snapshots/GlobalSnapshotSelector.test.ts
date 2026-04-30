import { describe, expect, it } from "vitest";

import { getSnapshotSelectionPath } from "./GlobalSnapshotSelector";

describe("getSnapshotSelectionPath", () => {
  it.each([
    ["/", 3, null],
    ["/snapshots", 3, null],
    ["/snapshots/7", 3, "/snapshots"],
    ["/snapshots/7/assets/100", 3, "/snapshots"],
    ["/snapshots/7/risk", 3, "/snapshots/3/risk"],
    ["/snapshots/7/migration", 3, "/snapshots/3/migration"],
    ["/snapshots/7/diff", 3, "/snapshots/3/diff"]
  ])("maps %s to %s", (pathname, snapshotId, expected) => {
    expect(getSnapshotSelectionPath(pathname, snapshotId)).toBe(expected);
  });
});
