import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { PerformanceEvaluationView } from "./PerformanceViews";

const run = {
  id: 44,
  snapshot_id: 3,
  baseline_snapshot_id: 2,
  trigger: "post_migration",
  profile: "smoke",
  status: "COMPLETED",
  thresholds: {},
  environment: { scenario: "testbed" },
  summary: {
    total_results: 1,
    by_status: { PASS: 0, WARN: 1, FAIL: 0, ERROR: 0 },
    average_deltas: { handshake_p95_percent: 18.2 },
    average_metrics: { handshake_success_rate: 0.965 },
    by_protocol: {
      TLS: {
        total_results: 1,
        by_status: { PASS: 0, WARN: 1, FAIL: 0, ERROR: 0 },
        average_metrics: { handshake_success_rate: 0.98 }
      },
      SSH: {
        total_results: 1,
        by_status: { PASS: 1, WARN: 0, FAIL: 0, ERROR: 0 },
        average_metrics: { handshake_success_rate: 0.95 }
      }
    },
    overall_status: "WARN"
  },
  started_at: "2026-05-01T00:00:00Z",
  completed_at: "2026-05-01T00:02:00Z",
  created_at: "2026-05-01T00:00:00Z"
} satisfies Schema<"PerformanceEvaluationRun">;

const detail = {
  ...run,
  results: [
    {
      id: 90,
      run_id: 44,
      asset_id: 7,
      asset_name: "web TLS leaf",
      bom_ref: "tls:web:leaf",
      target_label: "web.testbed.local:443",
      protocol: "TLS",
      status: "WARN",
      compatibility_status: "PASS",
      negotiated_algorithm: "ML-KEM-768+ECDHE",
      metrics: {
        handshake_ms: { p50: 40, p95: 118.2, samples: 30 },
        ttfb_ms: { p50: 80, p95: 160.4, samples: 30 },
        handshake_success_rate: 0.98,
        failure_rate: 0,
        timeout_rate: 0,
        handshake_bytes_sent: 3400,
        handshake_bytes_received: 5200
      },
      deltas: { handshake_p95_percent: 18.2 },
      signals: [{ level: "WARN", reason: "handshake_p95_percent_above_warn_threshold", value: 18.2 }],
      recommendation: "canary_more",
      error_message: "",
      measured_at: "2026-05-01T00:01:00Z"
    },
    {
      id: 91,
      run_id: 44,
      asset_id: 8,
      asset_name: "ssh host key",
      bom_ref: "ssh:host:rsa",
      target_label: "ssh.testbed.local:22",
      protocol: "SSH",
      status: "PASS",
      compatibility_status: "PASS",
      negotiated_algorithm: "curve25519-sha256 + ssh-rsa",
      metrics: {
        protocol: "SSH",
        handshake_ms: { p50: 20, p95: 40, samples: 20 },
        handshake_success_rate: 0.95,
        failure_rate: 0.05,
        timeout_rate: 0
      },
      deltas: { handshake_p95_percent: 0 },
      signals: [],
      recommendation: "proceed",
      error_message: "",
      measured_at: "2026-05-01T00:01:05Z"
    }
  ]
} satisfies Schema<"PerformanceEvaluationRunDetail">;

describe("PerformanceEvaluationView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders availability check run summary and asset measurements", async () => {
    vi.spyOn(services.performance, "listRuns").mockResolvedValue({ items: [run], total: 1, offset: 0, limit: 100 });
    vi.spyOn(services.performance, "getRun").mockResolvedValue(detail);

    renderWithApp(<PerformanceEvaluationView snapshotId={3} />);

    expect(await screen.findByText("스냅샷 #3 가용성 검사")).toBeInTheDocument();
    expect(await screen.findByText("tls:web:leaf")).toBeInTheDocument();
    expect(screen.getByText("ssh:host:rsa")).toBeInTheDocument();
    expect(screen.getByText("post_migration")).toBeInTheDocument();
    expect(screen.getByText("96.5%")).toBeInTheDocument();
    expect(screen.getByText("98.0%")).toBeInTheDocument();
    expect(screen.getByText("95.0%")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "프로토콜" })).toBeInTheDocument();
    expect(screen.getByText("SSH")).toBeInTheDocument();
    expect(screen.getByText("118.2 ms")).toBeInTheDocument();
    expect(screen.getByText("+18.2%")).toBeInTheDocument();
    expect(screen.getByText("canary_more")).toBeInTheDocument();
  });
});
