import { describe, expect, it } from "vitest";

import { formatSnapshotOptionLabel, getLatestSnapshotId, getSnapshotSelectionPath } from "./GlobalSnapshotSelector";

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

describe("snapshot option labels", () => {
  it("marks the newest snapshot as latest by created_at", () => {
    const snapshots = [
      { id: 1, created_at: "2026-04-29T00:00:00Z" },
      { id: 3, created_at: "2026-04-29T00:01:00Z" },
      { id: 2, created_at: "2026-04-30T00:00:00Z" }
    ];

    expect(getLatestSnapshotId(snapshots)).toBe(2);
    expect(formatSnapshotOptionLabel(snapshots[2], 2)).toMatch(/^최신 · #2 ·/);
    expect(formatSnapshotOptionLabel(snapshots[0], 2)).toMatch(/^#1 ·/);
  });

  it("uses the larger id as a tie breaker when timestamps match", () => {
    expect(
      getLatestSnapshotId([
        { id: 4, created_at: "2026-04-30T00:00:00Z" },
        { id: 5, created_at: "2026-04-30T00:00:00Z" }
      ])
    ).toBe(5);
  });
});
