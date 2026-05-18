import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { MigrationPlanView } from "./MigrationViews";

const migrationItem = {
  asset_id: 9001,
  asset_name: "cert-leaf-web-rsa2048",
  asset_type: "certificate",
  asset_purpose: "digital_signature",
  current: { algorithm: "RSA-2048", key_size_bits: 2048, quantum_vulnerable: true },
  recommendation: {
    strategy: "hybrid",
    target_algorithm: "ML-DSA-65",
    target_algorithm_set: ["ML-DSA-65"],
    final_algorithm_set: ["ML-DSA-65"],
    phase: "hybrid_first",
    blockers: ["runtime_capability_unknown"],
    rollback: "Keep an approved rollback path available.",
    validation: ["rescan_crypto_inventory"],
    rationale: "Use the PQC target after compatibility review.",
    confidence: 0.77
  },
  alternatives: [{ strategy: "replace", target_algorithm: "ML-DSA-65", trade_off: "requires client compatibility review" }],
  risk_score: 95,
  tier: "CRITICAL",
  agility: {
    score: 36,
    level: "LOW",
    blockers: ["runtime_capability_unknown"],
    enablers: ["inventory_fresh"]
  },
  playbook: [
    {
      order: 1,
      kind: "prepare_pqc_transition",
      title: "Prepare PQC transition",
      action: "Introduce ML-DSA-65 and validate service compatibility.",
      validation: "rescan_crypto_inventory"
    }
  ]
} satisfies Schema<"MigrationPlanItem">;

describe("MigrationPlanView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders crypto agility and playbook data from migration recommendations", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.migration, "plan").mockResolvedValue({ items: [migrationItem], total: 1, offset: 0, limit: 20 });
    vi.spyOn(services.migration, "impact").mockResolvedValue({
      selected_count: 1,
      hosts: ["web.testbed.local"],
      services: ["web.testbed.local:443"],
      cert_reissues: 1,
      config_changes: 1,
      key_regens: 0,
      estimated_downtime_min: 15
    });

    renderWithApp(<MigrationPlanView snapshotId={3} />);

    expect(await screen.findByRole("heading", { name: "스냅샷 #3 Review Targets" })).toBeInTheDocument();
    expect(screen.getByText("현재 화면은 전환 권고 검토와 보고서 생성 전용입니다. 인증서 재발급, 키 교체, 서비스 설정 변경은 수행하지 않습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "전환 대상 계획" })).toBeInTheDocument();
    expect(await screen.findByText("cert-leaf-web-rsa2048")).toBeInTheDocument();
    expect(screen.getByText("디지털 서명")).toBeInTheDocument();
    expect(screen.getByText("전환 검토")).toBeInTheDocument();
    expect(screen.getByText("PQC 전환")).toBeInTheDocument();
    expect(screen.getByText("36 · 낮음")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI 산출" })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "cert-leaf-web-rsa2048 선택" }));

    expect(await screen.findByText("암호 민첩성 플레이북")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "작업 항목" })).toBeInTheDocument();
    expect(screen.getByText("인증서 재발급")).toBeInTheDocument();
    expect(screen.getByText("15분")).toBeInTheDocument();
    expect(screen.getByText("web.testbed.local:443")).toBeInTheDocument();
    expect(screen.queryByText("selected_count")).not.toBeInTheDocument();
    expect(screen.getByText("runtime_capability_unknown")).toBeInTheDocument();
    expect(screen.getByText("Prepare PQC transition")).toBeInTheDocument();
    expect(screen.getByText("Keep an approved rollback path available.")).toBeInTheDocument();
  });

  it("applies guarded AI migration recommendations to the visible row", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.migration, "plan").mockResolvedValue({ items: [migrationItem], total: 1, offset: 0, limit: 20 });
    vi.spyOn(services.migration, "impact").mockResolvedValue({
      selected_count: 1,
      hosts: [],
      services: [],
      cert_reissues: 0,
      config_changes: 0,
      key_regens: 0,
      estimated_downtime_min: 0
    });
    vi.spyOn(services.migration, "aiSuggestion").mockResolvedValue({
      asset_id: migrationItem.asset_id,
      prompt_version: "migration-candidate-suggestion-v1",
      plan_item: {
        ...migrationItem,
        recommendation: {
          ...migrationItem.recommendation,
          strategy: "hybrid",
          target_algorithm: "ML-DSA-65",
          target_algorithm_set: ["ML-DSA-65"],
          final_algorithm_set: ["ML-DSA-65"],
          phase: "hybrid_first",
          rationale: "AI selected the allowed PQC target.",
          confidence: 0.88
        },
        ai_recommendation: {
          source: "llm_guarded_allowed_candidates",
          selected_candidate_id: "policy_default",
          evidence: ["service_role:payment"],
          fallback: { used: false, reason: null }
        }
      },
      provider: { provider: "codex-cli", model: "gpt-5.3-codex-spark", usage: {} },
      fallback: { used: false, reason: null },
      llm_trace: {
        request: { version: "migration-candidate-suggestion-v1", system: "system", user: "user", payload: {}, response_schema: {} },
        response: { raw: "{\"selected_candidate_id\":\"policy_default\"}", parsed: { selected_candidate_id: "policy_default" } }
      }
    });

    renderWithApp(<MigrationPlanView snapshotId={3} />);

    await screen.findByRole("button", { name: "AI 산출" });
    await user.click(screen.getByRole("button", { name: "AI 산출" }));

    expect((await screen.findAllByText("ML-DSA-65")).length).toBeGreaterThan(0);
    expect(screen.getByText("AI 목표 알고리즘 산출 상세")).toBeInTheDocument();
    expect(screen.getByText("AI selected the allowed PQC target.")).toBeInTheDocument();
    expect(screen.getByText("policy_default")).toBeInTheDocument();
    expect(screen.queryByText(/RSA-2048 \+ ML-DSA-65/)).not.toBeInTheDocument();
  });
});
