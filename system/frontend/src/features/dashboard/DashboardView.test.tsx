import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";
import { renderWithApp } from "../../test/test-utils";
import { DashboardView } from "./DashboardView";

describe("DashboardView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    useSnapshotSelectionStore.setState({ selectedSnapshotId: null });
  });

  it("renders onboarding empty state when no snapshot exists", async () => {
    vi.spyOn(services.dashboard, "summary").mockResolvedValue({
      snapshot: null,
      by_tier: {},
      by_asset_type: {},
      by_algorithm_family: {},
      quantum_vulnerable_ratio: { vulnerable: 0, safe: 0, unknown: 0 },
      kpis: {
        discovered_crypto_assets_per_scan: { value: 0, unit: "assets", source: "cbom_snapshot", snapshot_id: null, scan_job_id: null },
        quantum_vulnerable_assets_per_scan: {
          value: 0,
          unit: "assets",
          source: "algorithm_family_classification",
          snapshot_id: null,
          scan_job_id: null
        },
        expiring_certificates_90d_per_scan: {
          value: 0,
          unit: "certificates",
          source: "certificate_metadata_expires_at",
          snapshot_id: null,
          scan_job_id: null
        },
        dormant_private_keys_per_scan: {
          value: 0,
          unit: "keys",
          source: "asset_metadata_dormant_private_key",
          snapshot_id: null,
          scan_job_id: null
        },
        automated_inventory_runtime_minutes_per_scan: {
          value: 0,
          unit: "minutes",
          source: "scan_job_timestamps",
          snapshot_id: null,
          scan_job_id: null
        },
        full_pipeline_runtime_minutes: {
          value: 0,
          unit: "minutes",
          source: "pipeline_job_timestamps",
          snapshot_id: null,
          scan_job_id: null
        }
      },
      recent_jobs: [],
      agents_status: { total: 0, active: 0, stale: 0 },
      trend: []
    });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });
    vi.spyOn(services.snapshots, "assets").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    vi.spyOn(services.targets, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });

    renderWithApp(<DashboardView />);

    expect(await screen.findByText("아직 스냅샷이 없습니다")).toBeInTheDocument();
    expect(screen.getByText("탐색 대상 추가")).toBeInTheDocument();
    expect(screen.getAllByText("데모 데이터 로드").length).toBeGreaterThanOrEqual(1);
  });

  it("loads demo seed data from the dashboard", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.dashboard, "summary").mockResolvedValue({
      snapshot: null,
      by_tier: {},
      by_asset_type: {},
      by_algorithm_family: {},
      quantum_vulnerable_ratio: { vulnerable: 0, safe: 0, unknown: 0 },
      kpis: {
        discovered_crypto_assets_per_scan: { value: 0, unit: "assets", source: "cbom_snapshot", snapshot_id: null, scan_job_id: null },
        quantum_vulnerable_assets_per_scan: {
          value: 0,
          unit: "assets",
          source: "algorithm_family_classification",
          snapshot_id: null,
          scan_job_id: null
        },
        expiring_certificates_90d_per_scan: {
          value: 0,
          unit: "certificates",
          source: "certificate_metadata_expires_at",
          snapshot_id: null,
          scan_job_id: null
        },
        dormant_private_keys_per_scan: {
          value: 0,
          unit: "keys",
          source: "asset_metadata_dormant_private_key",
          snapshot_id: null,
          scan_job_id: null
        },
        automated_inventory_runtime_minutes_per_scan: {
          value: 0,
          unit: "minutes",
          source: "scan_job_timestamps",
          snapshot_id: null,
          scan_job_id: null
        },
        full_pipeline_runtime_minutes: {
          value: 0,
          unit: "minutes",
          source: "pipeline_job_timestamps",
          snapshot_id: null,
          scan_job_id: null
        }
      },
      recent_jobs: [],
      agents_status: { total: 0, active: 0, stale: 0 },
      trend: []
    });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });
    vi.spyOn(services.snapshots, "assets").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    vi.spyOn(services.targets, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    const seedSpy = vi.spyOn(services.dashboard, "seedDemo").mockResolvedValue({
      status: "loaded",
      reset: true,
      scenario: "testbed_demo",
      latest_snapshot_id: 22,
      baseline_snapshot_id: 21,
      asset_count: 67,
      message: "Seeded testbed-demo"
    });

    renderWithApp(<DashboardView />);
    await user.click((await screen.findAllByRole("button", { name: /데모 데이터 로드/ }))[0]!);

    await waitFor(() => expect(seedSpy).toHaveBeenCalledWith({ reset: true }));
    expect(useSnapshotSelectionStore.getState().selectedSnapshotId).toBe(22);
  });

  it("requests summary for the globally selected snapshot", async () => {
    useSnapshotSelectionStore.setState({ selectedSnapshotId: 2 });
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
      kpis: {
        discovered_crypto_assets_per_scan: {
          value: snapshotId === 2 ? 12 : 0,
          unit: "assets",
          source: "cbom_snapshot",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        },
        quantum_vulnerable_assets_per_scan: {
          value: snapshotId === 2 ? 5 : 0,
          unit: "assets",
          source: "algorithm_family_classification",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        },
        expiring_certificates_90d_per_scan: {
          value: snapshotId === 2 ? 2 : 0,
          unit: "certificates",
          source: "certificate_metadata_expires_at",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        },
        dormant_private_keys_per_scan: {
          value: snapshotId === 2 ? 3 : 0,
          unit: "keys",
          source: "asset_metadata_dormant_private_key",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        },
        automated_inventory_runtime_minutes_per_scan: {
          value: snapshotId === 2 ? 6 : 0,
          unit: "minutes",
          source: "scan_job_timestamps",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        },
        full_pipeline_runtime_minutes: {
          value: snapshotId === 2 ? 9 : 0,
          unit: "minutes",
          source: "pipeline_job_timestamps",
          snapshot_id: snapshotId ?? 1,
          scan_job_id: 44
        }
      },
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
    vi.spyOn(services.snapshots, "assets").mockResolvedValue({
      items: [
        {
          id: 100,
          snapshot_id: 2,
          bom_ref: "tls:web:leaf:rsa",
          asset_class: "crypto",
          asset_type: "certificate",
          name: "web.testbed.local TLS leaf certificate",
          target_id: 10,
          target_label: "web.testbed.local:443",
          summary: { algorithm: "RSA-2048", algorithm_family: "RSA" },
          risk: { score: 82, tier: "HIGH" }
        }
      ],
      total: 1,
      offset: 0,
      limit: 100
    });
    vi.spyOn(services.targets, "list").mockResolvedValue({
      items: [
        {
          id: 10,
          host: "web.testbed.local",
          display_name: "Web Server (RSA)",
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
          updated_at: "2026-04-29T00:00:00Z"
        }
      ],
      total: 1,
      offset: 0,
      limit: 100
    });

    renderWithApp(<DashboardView />);

    await waitFor(() => expect(summarySpy).toHaveBeenCalledWith(2));
    expect(await screen.findByText("스캔당 발견 자산")).toBeInTheDocument();
    expect(screen.getAllByText("스캔 #44").length).toBeGreaterThanOrEqual(2);
    expect((await screen.findAllByText("12")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("만료 임박 인증서")).toBeInTheDocument();
    expect(screen.getByText("90일 이내")).toBeInTheDocument();
    expect(screen.getByText("잠든 개인키")).toBeInTheDocument();
    expect(screen.getByText("미사용 파일")).toBeInTheDocument();
    expect(screen.getByText("자동화 실행 시간")).toBeInTheDocument();
    expect(screen.getByText("6분")).toBeInTheDocument();
    expect(screen.getByText("전체 파이프라인")).toBeInTheDocument();
    expect(screen.getByText("9분")).toBeInTheDocument();
    expect(screen.getByText("10분 이내")).toBeInTheDocument();
    expect(await screen.findByText("네트워크 암호 노출 현황")).toBeInTheDocument();
  });
});
