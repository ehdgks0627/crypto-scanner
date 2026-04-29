import { describe, expect, it } from "vitest";

import { queryKeys } from "./queryKeys";

describe("queryKeys", () => {
  it("keeps risk list prefix compatible with filtered list keys", () => {
    expect(queryKeys.risk.list(7, { tier: "CRITICAL" }).slice(0, 3)).toEqual(queryKeys.risk.listPrefix(7));
  });

  it("keeps snapshot asset prefix compatible with filtered asset keys", () => {
    expect(queryKeys.snapshots.assets(7, { tier: ["CRITICAL"] }).slice(0, 3)).toEqual(queryKeys.snapshots.assetsPrefix(7));
  });
});
