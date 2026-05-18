import type { Schema } from "../api/types";

export type MigrationPlanItemWithAi = Schema<"MigrationPlanItem"> & { ai_recommendation?: unknown };

export function hasAiRecommendation(item: MigrationPlanItemWithAi): boolean {
  return Boolean(item.ai_recommendation);
}

export function displayMigrationTargetAlgorithm(item: MigrationPlanItemWithAi): string {
  if (!hasAiRecommendation(item)) {
    return "-";
  }

  const finalAlgorithms = item.recommendation.final_algorithm_set.filter(Boolean);
  if (finalAlgorithms.length > 0) {
    return finalAlgorithms.join(" + ");
  }

  const currentAlgorithm = normalizeAlgorithm(item.current.algorithm);
  const targetAlgorithms = item.recommendation.target_algorithm_set.filter((algorithm) => normalizeAlgorithm(algorithm) !== currentAlgorithm);
  if (targetAlgorithms.length > 0) {
    return targetAlgorithms.join(" + ");
  }

  return item.recommendation.target_algorithm || "-";
}

export function displayMigrationRecommendation(item: MigrationPlanItemWithAi): string {
  if (!hasAiRecommendation(item)) {
    return "AI 산출 전";
  }
  return `${displayMigrationStrategy(item)} -> ${displayMigrationTargetAlgorithm(item)}`;
}

export function displayMigrationStrategy(item: MigrationPlanItemWithAi): string {
  if (item.recommendation.strategy === "no_change") {
    return "유지";
  }
  return "PQC 전환";
}

export function displayMigrationPhase(item: MigrationPlanItemWithAi): string {
  if (item.recommendation.phase === "monitor") {
    return "모니터링";
  }
  return "전환 검토";
}

function normalizeAlgorithm(value?: string | null): string {
  return (value ?? "").toLowerCase().replace(/[\s_]/g, "");
}
