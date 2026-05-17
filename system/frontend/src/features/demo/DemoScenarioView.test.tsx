import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DemoSession } from "../../api/demoTypes";
import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { DemoScenarioView } from "./DemoScenarioView";

describe("DemoScenarioView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the target step and advances with the next button", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("targets"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });
    const nextSpy = vi.spyOn(services.demo, "next").mockResolvedValue(makeSession("agents"));
    vi.spyOn(services.demo, "start").mockResolvedValue(makeSession("targets"));

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("최종 시연")).toBeInTheDocument();
    expect(screen.getByText("payments.demo.local")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /다음 단계/ }));

    await waitFor(() => expect(nextSpy).toHaveBeenCalled());
    expect(await screen.findByText("Discovery Agent 자산 28개 정리 완료")).toBeInTheDocument();
  });

  it("renders verification metrics at the final step", async () => {
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("verification"));
    vi.spyOn(services.demo, "events").mockResolvedValue({
      items: [{ step: "verification", message: "가용성 검증 PASS, 실패 경로 0건", progress: 100 }]
    });

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("4차원 가용성 검증")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("42->54ms")).toBeInTheDocument();
    expect(screen.getByText("실패 경로 0건")).toBeInTheDocument();
  });
});

function makeSession(stepId: DemoSession["current_step_id"]): DemoSession {
  const ids: DemoSession["current_step_id"][] = ["targets", "agents", "cbom", "risk", "migration", "verification"];
  const currentStep = ids.indexOf(stepId);
  return {
    scenario: "final_presentation_demo",
    current_step: currentStep,
    current_step_id: stepId,
    is_complete: stepId === "verification",
    resource_ids: {
      target_set: "demo-targets-v1",
      discovery: "demo-discovery-v1",
      scan: "demo-scan-v1",
      snapshot: "demo-cbom-v1",
      assessment: "demo-assessment-v1",
      migration: "demo-migration-v1",
      verification: "demo-verification-v1"
    },
    last_error: null,
    can_retry: true,
    steps: ids.map((id, index) => ({
      id,
      index,
      title: stepTitle(id),
      subtitle: `${id} subtitle`,
      status: index <= currentStep ? "completed" : "locked",
      progress: index <= currentStep ? 100 : 0
    })),
    targets: [
      { id: "scope-01", value: "10.0.0.0/24", kind: "CIDR", service: "사내 서브넷" },
      { id: "scope-02", value: "payments.demo.local", kind: "Domain", service: "외부 결제 API" }
    ],
    host_labels: [
      {
        host: "srv-01",
        description: "외부 결제 API",
        role: "edge-proxy",
        data_classes: ["PII", "payment"],
        partners: ["PG-A"],
        retention: "7y"
      }
    ],
    agent_run: {
      status: currentStep >= 1 ? "completed" : "pending",
      progress: currentStep >= 1 ? 100 : 0,
      total_assets: 47,
      discovery_assets: 28,
      host_assets: 24,
      overlap_assets: 5,
      active_keys: 44,
      dormant_keys: 3,
      algorithm_distribution: [{ label: "RSA", count: 14, quantum_vulnerable: true }],
      logs: {
        discovery: currentStep >= 1 ? ["Discovery Agent 자산 28개 정리 완료"] : [],
        host: currentStep >= 1 ? ["Host Agent 자산 24개 정리 완료"] : []
      }
    },
    assets: [
      {
        id: "srv-01:443/tls",
        host: "srv-01",
        domain: "api.payments.example.com",
        name: "TLS Endpoint",
        asset_type: "certificate",
        algorithm_group: "RSA",
        algorithm: "RSA-2048",
        key_size: 2048,
        expires: "2027-03-12",
        role: "edge-proxy",
        neighbors: ["payments-api"],
        data_tags: ["PII", "payment"],
        retention: "7y",
        discovered_by: ["discovery_agent", "host_agent"],
        priority: "P1",
        risk_score: 9.2,
        dormant: false,
        quantum_vulnerable: true
      }
    ],
    risk: {
      status: currentStep >= 3 ? "completed" : "pending",
      summary: { P1: 12, P2: 8, P3: 27 },
      example: currentStep >= 3
        ? {
            asset_id: "srv-01:443/tls",
            score: 9.2,
            priority: "P1",
            criteria: { value: { level: "HIGH", reason: "외부 결제 API" } }
          }
        : null
    },
    migration: {
      status: currentStep >= 4 ? "completed" : "pending",
      recommendation_count: 20,
      items: [
        {
          asset_id: "srv-01:443/tls",
          current_algorithm: "RSA-2048",
          recommended_algorithm: "ML-DSA-65",
          priority: "P1",
          reason: "장기 보호 가치와 양자 취약 공개키 사용이 확인됨"
        }
      ]
    },
    verification: currentStep >= 5
      ? {
          status: "completed",
          overall_status: "PASS",
          handshake_success_rate: 100,
          latency_before_ms: 42,
          latency_after_ms: 54,
          throughput_before_rps: 2400,
          throughput_after_rps: 2380,
          compatibility_before: 100,
          compatibility_after: 98,
          failure_count: 0,
          cbom_changes: 12,
          checks: [{ name: "회귀", status: "PASS", value: "실패 경로 0건" }]
        }
      : { status: "pending" }
  };
}

function stepTitle(id: DemoSession["current_step_id"]) {
  return {
    targets: "대상 등록",
    agents: "Agent 실행",
    cbom: "Enriched CBOM",
    risk: "AI 위험도 평가",
    migration: "PQC 매핑 추천",
    verification: "가용성 검증"
  }[id];
}
