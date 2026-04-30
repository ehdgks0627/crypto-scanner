import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";
import { renderWithApp } from "../../test/test-utils";
import { SnapshotsView } from "./SnapshotViews";

const snapshots = [
  {
    id: 2,
    scan_job_id: null,
    serial_number: "snap-2",
    asset_count: 1,
    created_at: "2026-04-29T00:01:00Z",
    summary: { by_tier: { CRITICAL: 1 } },
    validation_errors: []
  },
  {
    id: 1,
    scan_job_id: null,
    serial_number: "snap-1",
    asset_count: 0,
    created_at: "2026-04-29T00:00:00Z",
    summary: {},
    validation_errors: []
  }
] satisfies Schema<"CbomSnapshot">[];

const assets = {
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
      risk: { score: 92, tier: "CRITICAL" }
    }
  ],
  total: 1,
  offset: 0,
  limit: 100
} satisfies Schema<"AssetListPage">;

describe("SnapshotsView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    useSnapshotSelectionStore.setState({ selectedSnapshotId: null });
  });

  it("renders the selected snapshot asset list instead of a snapshot table", async () => {
    useSnapshotSelectionStore.setState({ selectedSnapshotId: 2 });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "get").mockImplementation(async (id) => snapshots.find((snapshot) => snapshot.id === id) ?? snapshots[0]);
    const assetsSpy = vi.spyOn(services.snapshots, "assets").mockResolvedValue(assets);

    renderWithApp(<SnapshotsView />);

    expect(await screen.findByText("web.testbed.local TLS leaf certificate")).toBeInTheDocument();
    expect(assetsSpy).toHaveBeenCalledWith(2, expect.objectContaining({ sort: "-risk_score" }));
    expect(screen.queryByText("Serial")).not.toBeInTheDocument();
  });

  it("keeps asset filters in the single-line toolbar layout", async () => {
    useSnapshotSelectionStore.setState({ selectedSnapshotId: 2 });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "get").mockResolvedValue(snapshots[0]);
    vi.spyOn(services.snapshots, "assets").mockResolvedValue(assets);

    renderWithApp(<SnapshotsView />);

    const search = await screen.findByLabelText("Asset search");
    expect(search.closest(".toolbar")).toHaveClass("toolbar--asset-filters");
    expect(search).toHaveClass("asset-filter-search");
    expect(screen.getByLabelText("Asset risk tier filter")).toHaveClass("asset-filter-tier");
  });

  it("defaults to the latest snapshot when no global snapshot was selected", async () => {
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "get").mockResolvedValue(snapshots[0]);
    const assetsSpy = vi.spyOn(services.snapshots, "assets").mockResolvedValue(assets);

    renderWithApp(<SnapshotsView />);

    await waitFor(() => expect(assetsSpy).toHaveBeenCalledWith(2, expect.any(Object)));
    expect(await screen.findByText("web.testbed.local TLS leaf certificate")).toBeInTheDocument();
  });
});
