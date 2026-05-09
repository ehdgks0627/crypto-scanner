import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { JobDetailView, ScanNewView } from "./JobViews";

function makeTarget(overrides: Partial<Schema<"Target">>): Schema<"Target"> {
  return {
    id: 1,
    host: "web.testbed.local",
    display_name: "Web Server",
    ip: "10.10.10.21",
    port: 443,
    protocol_hint: "TLS",
    sni: null,
    transport: "TCP",
    agent_enabled: false,
    agent_url: null,
    context: {
      sensitivity: null,
      lifespan_years: null,
      criticality: null,
      exposure: null,
      service_role: null
    },
    created_at: "2026-04-29T00:00:00Z",
    updated_at: "2026-04-29T00:00:00Z",
    ...overrides
  };
}

describe("ScanNewView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("selects every target and scanner by default", async () => {
    vi.spyOn(services.targets, "list").mockResolvedValue({
      items: [
        makeTarget({ id: 1, host: "web.testbed.local", display_name: "Web Server" }),
        makeTarget({ id: 2, host: "ssh.testbed.local", display_name: null, port: 22, protocol_hint: "SSH" })
      ],
      total: 2,
      offset: 0,
      limit: 100
    });
    vi.spyOn(services.meta, "scanners").mockResolvedValue({
      scanners: [
        { id: "network", label: "네트워크", requires_agent: false },
        { id: "agent.cert_store", label: "인증서 저장소", requires_agent: true }
      ]
    });

    renderWithApp(<ScanNewView />);

    expect(await screen.findByText("Web Server")).toBeInTheDocument();
    expect(await screen.findByText("네트워크")).toBeInTheDocument();

    await waitFor(() => {
      const checkboxes = screen.getAllByRole("checkbox");
      expect(checkboxes).toHaveLength(4);
      checkboxes.forEach((checkbox) => expect(checkbox).toBeChecked());
    });
    expect(screen.getByRole("button", { name: /스캔 시작/ })).toBeEnabled();
  });
});

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

    expect(await screen.findByText("작업 #7")).toBeInTheDocument();
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

  it("renders structured job and log errors as text", async () => {
    vi.spyOn(services.jobs, "get").mockResolvedValue({
      id: 14,
      kind: "scan_job",
      resource: { kind: "scan_job", id: 14 },
      status: "FAILED",
      progress: null,
      started_at: null,
      cancel_requested_at: null,
      finished_at: "2026-04-29T00:00:00Z",
      result: null,
      error: { code: "scan_failed", message: "Worker returned a structured failure" } as unknown as string
    });
    vi.spyOn(services.jobs, "logs").mockResolvedValue({
      items: [
        {
          id: 2,
          scan_job_id: 14,
          target_id: 5,
          target_label: "api.testbed.local:443",
          scanner_kind: "network",
          status: "ERROR",
          findings_count: 0,
          started_at: "2026-04-29T00:00:00Z",
          finished_at: "2026-04-29T00:01:00Z",
          error: { code: "handshake_failed", message: "TLS handshake failed" } as unknown as string
        }
      ],
      total: 1,
      offset: 0,
      limit: 100
    });

    renderWithApp(<JobDetailView id={14} />);

    expect(await screen.findByText("scan_failed: Worker returned a structured failure")).toBeInTheDocument();
    expect(screen.getByText("handshake_failed: TLS handshake failed")).toBeInTheDocument();
  });
});
