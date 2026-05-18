import type { Schema } from "../api/types";
import { formatDateTime, formatScore } from "../lib/format";
import { agilityLevelLabel, assetTypeLabel, migrationPurposeLabel, riskTierLabel } from "./displayLabels";

type MigrationPlanItem = Schema<"MigrationPlanItem">;
type MigrationPlanItemWithAi = MigrationPlanItem & { ai_recommendation?: unknown };
type MigrationImpact = Schema<"MigrationImpact">;

export class MigrationReportBuilder {
  constructor(
    private readonly snapshotId: number,
    private readonly items: MigrationPlanItemWithAi[],
    private readonly impact?: MigrationImpact,
    private readonly generatedAt = new Date()
  ) {}

  buildMarkdown(): string {
    const lines = [
      `# PQC 마이그레이션 보고서 - 스냅샷 #${this.snapshotId}`,
      "",
      `생성 시각: ${formatDateTime(this.generatedAt.toISOString())}`,
      `선택 자산: ${this.items.length}`,
      "",
      "## 영향도 요약",
      "",
      ...this.impactSummaryLines(),
      "",
      "## 선택 자산",
      "",
      ...this.assetLines(),
      "",
      "## 부록",
      "",
      "이 보고서는 전환 권고와 영향도 산정만 제공합니다. 인증서 재발급, 키 교체, 서비스 설정 변경은 수행하지 않으며, 실제 배포 전 서비스 호환성을 별도로 검증해야 합니다."
    ];

    return `${lines.join("\n")}\n`;
  }

  private impactSummaryLines(): string[] {
    if (!this.impact) {
      return ["보고서 생성 시점에 영향도 분석을 사용할 수 없었습니다."];
    }

    return [
      `- 호스트: ${this.impact.hosts.length ? this.impact.hosts.join(", ") : "-"}`,
      `- 서비스: ${this.impact.services.length ? this.impact.services.join(", ") : "-"}`,
      `- 인증서 재발급: ${this.impact.cert_reissues}`,
      `- 설정 변경: ${this.impact.config_changes}`,
      `- 키 재생성: ${this.impact.key_regens}`,
      `- 예상 다운타임: ${this.impact.estimated_downtime_min}분`
    ];
  }

  private assetLines(): string[] {
    if (this.items.length === 0) {
      return ["선택한 자산이 없습니다."];
    }

    return this.items.flatMap((item, index) => [
      `### ${index + 1}. ${item.asset_name}`,
      "",
      `- 자산 ID: ${item.asset_id}`,
      `- 타입: ${assetTypeLabel(item.asset_type)}`,
      `- 용도: ${migrationPurposeLabel(item.asset_purpose)}`,
      `- 위험도: ${formatScore(item.risk_score)} (${riskTierLabel(item.tier)})`,
      `- 현재: ${this.currentAlgorithm(item)}`,
      `- 권고: ${this.recommendation(item)}`,
      `- 단계: ${this.aiReady(item) ? item.recommendation.phase : "AI 산출 전"}`,
      `- 최종 알고리즘 세트: ${this.aiReady(item) ? item.recommendation.final_algorithm_set.join(", ") : "-"}`,
      `- 민첩성: ${item.agility.score}/100 (${agilityLevelLabel(item.agility.level)})`,
      `- 차단 요인: ${item.agility.blockers.length ? item.agility.blockers.join(", ") : "-"}`,
      `- 검증: ${item.recommendation.validation.length ? item.recommendation.validation.join(", ") : "-"}`,
      `- 롤백: ${item.recommendation.rollback}`,
      `- 근거: ${this.aiReady(item) ? item.recommendation.rationale : "목표 알고리즘 산출 전입니다."}`,
      `- 신뢰도: ${this.aiReady(item) ? `${Math.round(item.recommendation.confidence * 100)}%` : "-"}`,
      `- 대안: ${this.alternatives(item)}`,
      `- 플레이북: ${this.playbook(item)}`,
      ""
    ]);
  }

  private aiReady(item: MigrationPlanItemWithAi): boolean {
    return Boolean(item.ai_recommendation);
  }

  private recommendation(item: MigrationPlanItemWithAi): string {
    if (!this.aiReady(item)) {
      return "AI 산출 전";
    }
    return `${item.recommendation.strategy} -> ${item.recommendation.target_algorithm}`;
  }

  private currentAlgorithm(item: MigrationPlanItemWithAi): string {
    const algorithm = item.current.algorithm ?? "알 수 없음";
    const keySize = item.current.key_size_bits ? `/${item.current.key_size_bits}bit` : "";
    const quantum = item.current.quantum_vulnerable === true ? "양자취약" : item.current.quantum_vulnerable === false ? "양자안전" : "알 수 없음";
    return `${algorithm}${keySize} (${quantum})`;
  }

  private alternatives(item: MigrationPlanItemWithAi): string {
    if (item.alternatives.length === 0) {
      return "-";
    }

    return item.alternatives.map((alternative) => `${alternative.strategy} -> ${alternative.target_algorithm} (${alternative.trade_off})`).join("; ");
  }

  private playbook(item: MigrationPlanItemWithAi): string {
    if (item.playbook.length === 0) {
      return "-";
    }

    return item.playbook.map((step) => `${step.order}. ${step.title}: ${step.action}`).join("; ");
  }
}
