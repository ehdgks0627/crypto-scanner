import { describe, expect, it } from "vitest";

import { MigrationReportBuilder } from "./migrationReport";

describe("MigrationReportBuilder", () => {
  it("builds a markdown report from selected migration items and impact", () => {
    const report = new MigrationReportBuilder(
      56,
      [
        {
          asset_id: 9001,
          asset_name: "cert-leaf-web-rsa2048",
          asset_type: "certificate",
          current: { algorithm: "RSA", key_size_bits: 2048, quantum_vulnerable: true },
          recommendation: {
            strategy: "hybrid",
            target_algorithm: "ML-DSA-65 + ECDSA-P256",
            rationale: "Public TLS certificate should migrate before long-lived exposure increases.",
            confidence: 0.82
          },
          alternatives: [{ strategy: "replace", target_algorithm: "ML-DSA-65", trade_off: "requires client compatibility review" }],
          risk_score: 91,
          tier: "CRITICAL"
        }
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

    expect(report).toContain("# PQC Migration Report - Snapshot #56");
    expect(report).toContain("Selected assets: 1");
    expect(report).toContain("- Hosts: api.testbed.local");
    expect(report).toContain("### 1. cert-leaf-web-rsa2048");
    expect(report).toContain("- Current: RSA/2048bit (quantum-vulnerable)");
    expect(report).toContain("- Recommendation: hybrid -> ML-DSA-65 + ECDSA-P256");
    expect(report).toContain("replace -> ML-DSA-65");
  });

  it("renders fallback sections when selection and impact are absent", () => {
    const report = new MigrationReportBuilder(7, [], undefined, new Date("2026-04-29T00:00:00Z")).buildMarkdown();

    expect(report).toContain("Impact analysis was not available");
    expect(report).toContain("No assets were selected.");
  });

  it("renders alternative fallback for assets without alternatives", () => {
    const report = new MigrationReportBuilder(
      7,
      [
        {
          asset_id: 3,
          asset_name: "safe-protocol",
          asset_type: "protocol",
          current: { algorithm: "ML-KEM", key_size_bits: null, quantum_vulnerable: false },
          recommendation: {
            strategy: "no_change",
            target_algorithm: "ML-KEM",
            rationale: "Already PQC ready.",
            confidence: 0.9
          },
          alternatives: [],
          risk_score: 12,
          tier: "LOW"
        }
      ],
      undefined,
      new Date("2026-04-29T00:00:00Z")
    ).buildMarkdown();

    expect(report).toContain("- Current: ML-KEM (quantum-safe)");
    expect(report).toContain("- Alternatives: -");
  });
});
