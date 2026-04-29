import { describe, expect, it } from "vitest";

import { ScanSelectionModel } from "./scanSelection";

describe("ScanSelectionModel", () => {
  it("prefers a single target_id query param", () => {
    expect(ScanSelectionModel.targetIdsFromSearch(new URLSearchParams("target_id=7&target_ids=1,2"))).toEqual([7]);
  });

  it("deduplicates CSV target_ids and ignores invalid values", () => {
    expect(ScanSelectionModel.targetIdsFromSearch(new URLSearchParams("target_ids=1,2,2,abc,-3,4"))).toEqual([1, 2, 4]);
  });
});
