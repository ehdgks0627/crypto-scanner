import type { RiskTier } from "../api/types";

export const riskTierOptions: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export function parseRiskTierParam(value: string | null): RiskTier | "" {
  return value && riskTierOptions.includes(value as RiskTier) ? (value as RiskTier) : "";
}
