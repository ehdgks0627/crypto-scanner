import { describe, expect, it } from "vitest";

import { JobProgressModel, SnapshotSummaryModel } from "./models";

describe("domain models", () => {
  it("calculates bounded job progress", () => {
    expect(new JobProgressModel({ completed: 4, total: 8 }).percent()).toBe(50);
    expect(new JobProgressModel({ completed: 9, total: 8 }).percent()).toBe(100);
    expect(new JobProgressModel(null).percent()).toBe(0);
  });

  it("formats snapshot labels", () => {
    expect(new SnapshotSummaryModel(null).label()).toBe("스냅샷 없음");
    expect(new SnapshotSummaryModel({ id: 3, created_at: "2026-04-29T00:00:00Z", asset_count: 12 }).label()).toContain("#3");
  });
});
