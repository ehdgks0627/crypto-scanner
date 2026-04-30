import { screen } from "@testing-library/react";
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

    expect(await screen.findByText("Snapshot #3 Risk")).toBeInTheDocument();
    expect((await screen.findAllByText("web.testbed.local TLS leaf certificate")).length).toBeGreaterThanOrEqual(1);
    for (const header of ["A", "D", "E", "L", "C"]) {
      expect(screen.getAllByRole("columnheader", { name: header }).length).toBeGreaterThanOrEqual(1);
    }
    expect(screen.getAllByText("0.95").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("1.00").length).toBeGreaterThanOrEqual(1);
  });
});
