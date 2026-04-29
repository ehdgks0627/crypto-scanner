import type { RiskWeightsInput } from "../api/types";

export function areRiskWeightsValid(weights: RiskWeightsInput): boolean {
  return Object.values(weights).every((value) => Number.isFinite(value) && value >= 0.5 && value <= 2);
}

export function updateRiskWeight(weights: RiskWeightsInput, key: keyof RiskWeightsInput, rawValue: string): RiskWeightsInput {
  return {
    ...weights,
    [key]: rawValue === "" ? Number.NaN : Number(rawValue)
  };
}
