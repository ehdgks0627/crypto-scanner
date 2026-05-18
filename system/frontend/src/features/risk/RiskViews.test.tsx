import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { RiskAssessmentView } from "./RiskViews";

const weights = {
  wA: 1,
  wD: 1,
  wE: 1,
  wL: 1,
  wC: 1,
  updated_at: "2026-04-30T00:00:00Z"
} satisfies Schema<"RiskWeightsState">;

const riskScore = {
  asset_id: 7,
  asset_name: "web.testbed.local TLS leaf certificate",
  asset_type: "certificate",
  score: 95,
  tier: "CRITICAL",
  factors: { a: 0.95, d: 1, e: 1, l: 1, c: 1 },
  dhs_risk: {
    score_10: 8.2,
    priority: "P1",
    weighted_raw: 0.82,
    weights: { protection_duration: 1.6 },
    criteria: {},
    missing_criteria: [],
    engine_version: "dhs-risk-v1"
  },
  computed_at: "2026-04-30T00:00:00Z"
} satisfies Schema<"RiskScore">;

describe("RiskAssessmentView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders risk scores with factor breakdown columns", async () => {
    vi.spyOn(services.risk, "weights").mockResolvedValue(weights);
    vi.spyOn(services.risk, "list").mockResolvedValue({ items: [riskScore], total: 1, offset: 0, limit: 20 });
    vi.spyOn(services.risk, "top").mockResolvedValue({ items: [riskScore], total: 1, offset: 0, limit: 10 });

    renderWithApp(<RiskAssessmentView snapshotId={3} />);

    expect(await screen.findByText("스냅샷 #3 위험평가")).toBeInTheDocument();
    expect(screen.getByText("위험 점수 계산식")).toBeInTheDocument();
    expect(screen.getByText("점수 = round(100 × A' × avg(D', E', L', C'))")).toBeInTheDocument();
    const weightGroup = screen.getByRole("group", { name: "위험 가중치 입력" });
    expect(weightGroup).toHaveClass("risk-weight-grid");
    expect(within(weightGroup).getAllByRole("spinbutton")).toHaveLength(5);
    expect((await screen.findAllByText("web.testbed.local TLS leaf certificate")).length).toBeGreaterThanOrEqual(1);
    for (const header of ["A", "D", "E", "L", "C"]) {
      expect(screen.getAllByRole("columnheader", { name: `${header} 계수` }).length).toBeGreaterThanOrEqual(1);
    }
    expect(screen.getAllByRole("columnheader", { name: "DHS 점수" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("columnheader", { name: "우선순위" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("8.2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("P1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("0.95").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("1.00").length).toBeGreaterThanOrEqual(1);
  });
});
