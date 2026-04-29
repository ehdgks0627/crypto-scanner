import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { JobDetailView } from "./JobViews";

describe("JobDetailView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("disables cancel for running recompute jobs and renders log errors", async () => {
    vi.spyOn(services.jobs, "get").mockResolvedValue({
      id: 7,
      kind: "recompute",
      resource: { kind: "recompute", id: 7 },
      status: "RUNNING",
      progress: null,
      started_at: null,
      cancel_requested_at: null,
      finished_at: null,
      result: null,
      error: null
    });
    vi.spyOn(services.jobs, "logs").mockRejectedValue(new ApiError("Logs failed", { status: 500 }));

    renderWithApp(<JobDetailView id={7} />);

    expect(await screen.findByText("Job #7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /취소/ })).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent("Logs failed");
  });

  it("renders successful run log rows", async () => {
    vi.spyOn(services.jobs, "get").mockResolvedValue({
      id: 8,
      kind: "scan_job",
      resource: { kind: "scan_job", id: 3 },
      status: "COMPLETED",
      progress: null,
      started_at: null,
      cancel_requested_at: null,
      finished_at: "2026-04-29T00:00:00Z",
      result: { snapshot_id: 4 },
      error: null
    });
    vi.spyOn(services.jobs, "logs").mockResolvedValue({
      items: [
        {
          id: 1,
          scan_job_id: 8,
          target_id: 2,
          target_label: "api.testbed.local:443",
          scanner_kind: "network",
          status: "SUCCESS",
          findings_count: 3,
          started_at: "2026-04-29T00:00:00Z",
          finished_at: "2026-04-29T00:01:00Z",
          error: null
        }
      ],
      total: 1,
      offset: 0,
      limit: 100
    });

    renderWithApp(<JobDetailView id={8} />);

    expect(await screen.findByText("api.testbed.local:443")).toBeInTheDocument();
    expect(screen.getByText("network")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
