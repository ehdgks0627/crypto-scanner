import type { Schema } from "../api/types";
import { formatDateTime, formatScore } from "../lib/format";

type MigrationPlanItem = Schema<"MigrationPlanItem">;
type MigrationImpact = Schema<"MigrationImpact">;

export class MigrationReportBuilder {
  constructor(
    private readonly snapshotId: number,
    private readonly items: MigrationPlanItem[],
    private readonly impact?: MigrationImpact,
    private readonly generatedAt = new Date()
  ) {}

  buildMarkdown(): string {
    const lines = [
      `# PQC Migration Report - Snapshot #${this.snapshotId}`,
      "",
      `Generated: ${formatDateTime(this.generatedAt.toISOString())}`,
      `Selected assets: ${this.items.length}`,
      "",
      "## Impact Summary",
      "",
      ...this.impactSummaryLines(),
      "",
      "## Selected Assets",
      "",
      ...this.assetLines(),
      "",
      "## Appendix",
      "",
      "Risk score and tier are calculated by the backend risk model. Recommendations are advisory and should be validated against service compatibility before rollout."
    ];

    return `${lines.join("\n")}\n`;
  }

  private impactSummaryLines(): string[] {
    if (!this.impact) {
      return ["Impact analysis was not available when this report was generated."];
    }

    return [
      `- Hosts: ${this.impact.hosts.length ? this.impact.hosts.join(", ") : "-"}`,
      `- Services: ${this.impact.services.length ? this.impact.services.join(", ") : "-"}`,
      `- Certificate reissues: ${this.impact.cert_reissues}`,
      `- Configuration changes: ${this.impact.config_changes}`,
      `- Key regenerations: ${this.impact.key_regens}`,
      `- Estimated downtime: ${this.impact.estimated_downtime_min} minutes`
    ];
  }

  private assetLines(): string[] {
    if (this.items.length === 0) {
      return ["No assets were selected."];
    }

    return this.items.flatMap((item, index) => [
      `### ${index + 1}. ${item.asset_name}`,
      "",
      `- Asset ID: ${item.asset_id}`,
      `- Type: ${item.asset_type}`,
      `- Risk: ${formatScore(item.risk_score)} (${item.tier})`,
      `- Current: ${this.currentAlgorithm(item)}`,
      `- Recommendation: ${item.recommendation.strategy} -> ${item.recommendation.target_algorithm}`,
      `- Rationale: ${item.recommendation.rationale}`,
      `- Confidence: ${Math.round(item.recommendation.confidence * 100)}%`,
      `- Alternatives: ${this.alternatives(item)}`,
      ""
    ]);
  }

  private currentAlgorithm(item: MigrationPlanItem): string {
    const algorithm = item.current.algorithm ?? "unknown";
    const keySize = item.current.key_size_bits ? `/${item.current.key_size_bits}bit` : "";
    const quantum = item.current.quantum_vulnerable === true ? "quantum-vulnerable" : item.current.quantum_vulnerable === false ? "quantum-safe" : "unknown";
    return `${algorithm}${keySize} (${quantum})`;
  }

  private alternatives(item: MigrationPlanItem): string {
    if (item.alternatives.length === 0) {
      return "-";
    }

    return item.alternatives.map((alternative) => `${alternative.strategy} -> ${alternative.target_algorithm} (${alternative.trade_off})`).join("; ");
  }
}
