import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DemoSession } from "../../api/demoTypes";
import { services } from "../../api/services";
import { DemoPage } from "../../pages/DemoPage";
import { renderWithApp } from "../../test/test-utils";
import { DemoScenarioView } from "./DemoScenarioView";

describe("DemoScenarioView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the /demo route", async () => {
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("targets"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });

    renderDemoRoute();

    expect(await screen.findByText("최종 시연")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "IP / Domain / CIDR" })).toHaveValue("10.0.0.0/24");
  });

  it("renders the target step and advances with the next button", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("targets"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });
    const nextSpy = vi.spyOn(services.demo, "next").mockResolvedValue(makeSession("agents"));
    vi.spyOn(services.demo, "start").mockResolvedValue(makeSession("targets"));

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("최종 시연")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "IP / Domain / CIDR" })).toHaveValue("10.0.0.0/24");
    expect(screen.getByRole("button", { name: "대상 추가" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "role" })).toHaveValue("edge-proxy");
    expect(screen.getByText("payments.demo.local")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /다음 단계/ }));

    await waitFor(() => expect(nextSpy).toHaveBeenCalled());
    expect(await screen.findByText("Discovery Agent 자산 28개 정리 완료")).toBeInTheDocument();
    expect(screen.getByText("47 / 47 자산 정리 완료")).toBeInTheDocument();
    expect(screen.getByText("잠든 키")).toBeInTheDocument();
  });

  it("renders CBOM, risk, and migration presentation details", async () => {
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("cbom"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });

    const { unmount } = renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("CBOM 자산 목록")).toBeInTheDocument();
    expect(screen.getByText("도메인")).toBeInTheDocument();
    expect(screen.getByText("연결 대상")).toBeInTheDocument();
    expect(screen.getByText("api.payments.example.com")).toBeInTheDocument();

    unmount();
    vi.restoreAllMocks();
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("risk"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });

    const riskRender = renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("DHS 6기준 평가 진행")).toBeInTheDocument();
    expect(screen.getByText("47 / 47 자산 평가 완료")).toBeInTheDocument();
    expect(screen.getByText("선택 자산 DHS 응답")).toBeInTheDocument();
    expect(screen.getByText("완료")).toBeInTheDocument();

    riskRender.unmount();
    vi.restoreAllMocks();
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("migration"));
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("추천 대상 20개")).toBeInTheDocument();
    expect(screen.getByText("자동 변경이 아니라 전환 계획 추천입니다.")).toBeInTheDocument();
    expect(screen.getByText("ML-DSA-65")).toBeInTheDocument();
  });

  it("renders retry state and disables next when a step fails", async () => {
    vi.spyOn(services.demo, "session").mockResolvedValue(makeErroredSession());
    vi.spyOn(services.demo, "events").mockResolvedValue({ items: [] });
    vi.spyOn(services.demo, "next").mockResolvedValue(makeSession("agents"));
    vi.spyOn(services.demo, "start").mockResolvedValue(makeSession("targets"));

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("단계 실행 실패")).toBeInTheDocument();
    expect(screen.getByText("Discovery Agent timeout")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /다음 단계/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "재시도" })).toBeInTheDocument();
  });

  it("renders verification metrics at the final step", async () => {
    vi.spyOn(services.demo, "session").mockResolvedValue(makeSession("verification"));
    vi.spyOn(services.demo, "events").mockResolvedValue({
      items: [{ step: "verification", message: "가용성 검증 PASS, 실패 경로 0건", progress: 100 }]
    });

    renderWithApp(<DemoScenarioView />);

    expect(await screen.findByText("4차원 가용성 검증")).toBeInTheDocument();
    expect(screen.getAllByText("PASS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
    expect(screen.getByText("42->54ms")).toBeInTheDocument();
    expect(screen.getByText("실패 경로 0건")).toBeInTheDocument();
  });
});

function renderDemoRoute() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  const router = createMemoryRouter([{ path: "/demo", element: <DemoPage /> }], { initialEntries: ["/demo"] });

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

function makeErroredSession(): DemoSession {
  return {
    ...makeSession("targets"),
    last_error: "Discovery Agent timeout",
    can_retry: true
  };
}

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
