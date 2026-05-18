import { describe, expect, it } from "vitest";

import type { Schema } from "../api/types";
import { MigrationReportBuilder } from "./migrationReport";

describe("MigrationReportBuilder", () => {
  it("builds a markdown report from selected migration items and impact", () => {
    const report = new MigrationReportBuilder(
      56,
      [
        makeMigrationItem({
          asset_id: 9001,
          asset_name: "cert-leaf-web-rsa2048",
          asset_type: "certificate",
          asset_purpose: "digital_signature",
          current: { algorithm: "RSA", key_size_bits: 2048, quantum_vulnerable: true },
          recommendation: {
            strategy: "hybrid",
            target_algorithm: "ML-DSA-65 + ECDSA-P256",
            target_algorithm_set: ["ML-DSA-65", "ECDSA-P256"],
            final_algorithm_set: ["ML-DSA-65"],
            phase: "hybrid_first",
            blockers: ["runtime_capability_unknown"],
            rollback: "Keep the existing RSA path enabled.",
            validation: ["rescan_crypto_inventory"],
            rationale: "Public TLS certificate should migrate before long-lived exposure increases.",
            confidence: 0.82
          },
          ai_recommendation: {
            source: "llm_guarded_allowed_candidates",
            selected_candidate_id: "policy_default",
            evidence: [],
            fallback: { used: false, reason: null }
          },
          alternatives: [{ strategy: "replace", target_algorithm: "ML-DSA-65", trade_off: "requires client compatibility review" }],
          risk_score: 91,
          tier: "CRITICAL",
          agility: { score: 45, level: "MEDIUM", blockers: ["runtime_capability_unknown"], enablers: ["config_policy"] },
          playbook: [{ order: 1, kind: "enable_hybrid", title: "Enable hybrid transition", action: "Deploy hybrid certificate.", validation: "Rescan." }]
        })
      ],
      {
        selected_count: 1,
        hosts: ["api.testbed.local"],
        services: ["TLS:443"],
        cert_reissues: 1,
        config_changes: 2,
        key_regens: 0,
        estimated_downtime_min: 5
      },
      new Date("2026-04-29T00:00:00Z")
    ).buildMarkdown();

    expect(report).toContain("# PQC 마이그레이션 보고서 - 스냅샷 #56");
    expect(report).toContain("선택 자산: 1");
    expect(report).toContain("- 호스트: api.testbed.local");
    expect(report).toContain("### 1. cert-leaf-web-rsa2048");
    expect(report).toContain("- 용도: 디지털 서명");
    expect(report).toContain("- 현재: RSA/2048bit (양자취약)");
    expect(report).toContain("- 권고: hybrid -> ML-DSA-65 + ECDSA-P256");
    expect(report).toContain("- 민첩성: 45/100 (보통)");
    expect(report).toContain("- 플레이북: 1. Enable hybrid transition: Deploy hybrid certificate.");
    expect(report).toContain("replace -> ML-DSA-65");
  });

  it("renders fallback sections when selection and impact are absent", () => {
    const report = new MigrationReportBuilder(7, [], undefined, new Date("2026-04-29T00:00:00Z")).buildMarkdown();

    expect(report).toContain("보고서 생성 시점에 영향도 분석을 사용할 수 없었습니다.");
    expect(report).toContain("선택한 자산이 없습니다.");
  });

  it("renders alternative fallback for assets without alternatives", () => {
    const report = new MigrationReportBuilder(
      7,
      [
        makeMigrationItem({
          asset_id: 3,
          asset_name: "safe-protocol",
          asset_type: "protocol",
          asset_purpose: "key_exchange",
          current: { algorithm: "ML-KEM", key_size_bits: null, quantum_vulnerable: false },
          recommendation: {
            strategy: "no_change",
            target_algorithm: "ML-KEM",
            target_algorithm_set: ["ML-KEM"],
            final_algorithm_set: ["ML-KEM"],
            phase: "monitor",
            blockers: [],
            rollback: "No rollout is required.",
            validation: ["periodic_rescan"],
            rationale: "Already PQC ready.",
            confidence: 0.9
          },
          alternatives: [],
          risk_score: 12,
          tier: "LOW",
          agility: { score: 85, level: "HIGH", blockers: [], enablers: ["automated_rotation"] },
          playbook: [{ order: 1, kind: "monitor", title: "Monitor cryptographic posture", action: "Rescan periodically.", validation: "Confirm unchanged." }]
        })
      ],
      undefined,
      new Date("2026-04-29T00:00:00Z")
    ).buildMarkdown();

    expect(report).toContain("- 현재: ML-KEM (양자안전)");
    expect(report).toContain("- 권고: AI 산출 전");
    expect(report).toContain("- 대안: -");
  });
});

function makeMigrationItem(overrides: Schema<"MigrationPlanItem"> & { ai_recommendation?: unknown }) {
  return overrides;
}
