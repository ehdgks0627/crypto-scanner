import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { DashboardView } from "./DashboardView";

describe("DashboardView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders onboarding empty state when no snapshot exists", async () => {
    vi.spyOn(services.dashboard, "summary").mockResolvedValue({
      snapshot: null,
      by_tier: {},
      by_asset_type: {},
      by_algorithm_family: {},
      quantum_vulnerable_ratio: { vulnerable: 0, safe: 0, unknown: 0 },
      recent_jobs: [],
      agents_status: { total: 0, active: 0, stale: 0 },
      trend: []
    });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });

    renderWithApp(<DashboardView />);

    expect(await screen.findByText("아직 스냅샷이 없습니다")).toBeInTheDocument();
    expect(screen.getByText("디스커버리 시작")).toBeInTheDocument();
  });

  it("requests summary for the selected snapshot", async () => {
    const user = userEvent.setup();
    const summarySpy = vi.spyOn(services.dashboard, "summary").mockImplementation(async (snapshotId) => ({
      snapshot: {
        id: snapshotId ?? 1,
        scan_job_id: null,
        serial_number: `snap-${snapshotId ?? 1}`,
        asset_count: snapshotId === 2 ? 12 : 0,
        created_at: "2026-04-29T00:00:00Z",
        summary: {},
        validation_errors: []
      },
      by_tier: { CRITICAL: snapshotId === 2 ? 3 : 0 },
      by_asset_type: { certificate: 12 },
      by_algorithm_family: { RSA: 8 },
      quantum_vulnerable_ratio: { vulnerable: snapshotId === 2 ? 5 : 0, safe: 7, unknown: 0 },
      recent_jobs: [],
      agents_status: { total: 2, active: 1, stale: 1 },
      trend: [{ snapshot_id: snapshotId ?? 1, created_at: "2026-04-29T00:00:00Z", critical_count: 3, total_count: 12 }]
    }));
    vi.spyOn(services.snapshots, "list").mockResolvedValue({
      items: [
        { id: 1, scan_job_id: null, serial_number: "snap-1", asset_count: 0, created_at: "2026-04-29T00:00:00Z", summary: {}, validation_errors: [] },
        { id: 2, scan_job_id: null, serial_number: "snap-2", asset_count: 0, created_at: "2026-04-29T00:01:00Z", summary: {}, validation_errors: [] }
      ],
      total: 2,
      offset: 0,
      limit: 20
    });

    renderWithApp(<DashboardView />);

    await user.selectOptions(await screen.findByLabelText("Dashboard snapshot selector"), "2");

    expect(summarySpy).toHaveBeenCalledWith(2);
    expect((await screen.findAllByText(/^#2/)).length).toBeGreaterThan(0);
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
