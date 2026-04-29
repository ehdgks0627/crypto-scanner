import { describe, expect, it } from "vitest";

import { areRiskWeightsValid, updateRiskWeight } from "./riskWeights";

describe("risk weights helpers", () => {
  it("validates the backend accepted 0.5-2.0 range", () => {
    expect(areRiskWeightsValid({ wA: 0.5, wD: 1, wE: 1.2, wL: 2, wC: 1 })).toBe(true);
    expect(areRiskWeightsValid({ wA: 0.49, wD: 1, wE: 1, wL: 1, wC: 1 })).toBe(false);
    expect(areRiskWeightsValid({ wA: 1, wD: 1, wE: Number.NaN, wL: 1, wC: 1 })).toBe(false);
  });

  it("treats blank number input as invalid instead of zero", () => {
    const weights = updateRiskWeight({ wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 }, "wA", "");

    expect(areRiskWeightsValid(weights)).toBe(false);
  });
});
