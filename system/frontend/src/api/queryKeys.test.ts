import { describe, expect, it } from "vitest";

import { queryKeys } from "./queryKeys";

describe("queryKeys", () => {
  it("keeps risk list prefix compatible with filtered list keys", () => {
    expect(queryKeys.risk.list(7, { tier: "CRITICAL" }).slice(0, 3)).toEqual(queryKeys.risk.listPrefix(7));
  });

  it("keeps snapshot asset prefix compatible with filtered asset keys", () => {
    expect(queryKeys.snapshots.assets(7, { tier: ["CRITICAL"] }).slice(0, 3)).toEqual(queryKeys.snapshots.assetsPrefix(7));
  });

  it("keeps agent list prefix compatible with active-state filters", () => {
    expect(queryKeys.agents.list(true).slice(0, 2)).toEqual(queryKeys.agents.listPrefix);
    expect(queryKeys.agents.list(false).slice(0, 2)).toEqual(queryKeys.agents.listPrefix);
  });

  it("keeps performance run prefix compatible with filtered run keys", () => {
    expect(queryKeys.performance.runs(7, { status: "COMPLETED" }).slice(0, 3)).toEqual(queryKeys.performance.runsPrefix(7));
  });
});
