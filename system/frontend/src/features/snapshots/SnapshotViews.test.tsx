import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";
import { renderWithApp } from "../../test/test-utils";
import { AssetDetailView, SnapshotDiffView, SnapshotsView } from "./SnapshotViews";

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
      risk: {
        score: 92,
        tier: "CRITICAL",
        dhs_risk: {
          score_10: 8.2,
          priority: "P1",
          weighted_raw: 0.82,
          weights: { protection_duration: 1.6 },
          criteria: {},
          missing_criteria: [],
          engine_version: "dhs-risk-v1"
        }
      }
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
    expect(screen.getByRole("columnheader", { name: "DHS 점수" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "우선순위" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Targets" })).toBeInTheDocument();
    expect(screen.getByText("8.2")).toBeInTheDocument();
    expect(screen.getByText("P1")).toBeInTheDocument();
    expect(screen.queryByText("Serial")).not.toBeInTheDocument();
  });

  it("keeps asset filters in the single-line toolbar layout", async () => {
    useSnapshotSelectionStore.setState({ selectedSnapshotId: 2 });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "get").mockResolvedValue(snapshots[0]);
    vi.spyOn(services.snapshots, "assets").mockResolvedValue(assets);

    renderWithApp(<SnapshotsView />);

    const search = await screen.findByLabelText("자산 검색");
    expect(search.closest(".toolbar")).toHaveClass("toolbar--asset-filters");
    expect(search).toHaveClass("asset-filter-search");
    expect(screen.getByLabelText("자산 위험도 필터")).toHaveClass("asset-filter-tier");
  });

  it("defaults to the latest snapshot when no global snapshot was selected", async () => {
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "get").mockResolvedValue(snapshots[0]);
    const assetsSpy = vi.spyOn(services.snapshots, "assets").mockResolvedValue(assets);

    renderWithApp(<SnapshotsView />);

    await waitFor(() => expect(assetsSpy).toHaveBeenCalledWith(2, expect.any(Object)));
    expect(await screen.findByText("web.testbed.local TLS leaf certificate")).toBeInTheDocument();
  });

  it("renders an empty state instead of requesting a stale stored snapshot", async () => {
    useSnapshotSelectionStore.setState({ selectedSnapshotId: 3 });
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    const getSpy = vi.spyOn(services.snapshots, "get");
    const assetsSpy = vi.spyOn(services.snapshots, "assets");

    renderWithApp(<SnapshotsView />);

    expect(await screen.findByText("식별 자산이 없습니다")).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
    expect(assetsSpy).not.toHaveBeenCalled();
  });
});

describe("AssetDetailView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("edits context inline with current effective values prefilled", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.assets, "get").mockResolvedValue(makeAssetDetail());
    const patchSpy = vi.spyOn(services.assets, "patchContext");
    vi.spyOn(services.performance, "history").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });

    renderWithApp(<AssetDetailView snapshotId={2} assetId={84} />);

    await screen.findByRole("heading", { name: "asset detail certificate", level: 1 });
    await user.click(screen.getByRole("button", { name: /컨텍스트 수정/ }));

    const contextCard = screen.getByRole("heading", { name: "평가 기준 컨텍스트" }).closest(".ui-card") as HTMLElement;
    expect(contextCard).not.toBeNull();
    expect(screen.queryByRole("heading", { name: "컨텍스트 재정의" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /override 사용/ })).not.toBeInTheDocument();
    expect(within(contextCard).queryByRole("option", { name: "재정의 없음" })).not.toBeInTheDocument();
    expect(within(contextCard).getAllByRole("option", { name: "미지정" })).toHaveLength(3);
    expect(within(contextCard).getByLabelText("민감도 수정 값")).toHaveValue("high");
    expect(within(contextCard).getByLabelText("중요도 수정 값")).toHaveValue("high");
    expect(within(contextCard).getByLabelText("노출 범위 수정 값")).toHaveValue("internal_network");
    expect(within(contextCard).getAllByText("현재 적용값: 높음 · 출처: 스캔 대상")).toHaveLength(2);
    expect(within(contextCard).getByText("현재 적용값: 10 · 출처: 스캔 대상")).toBeInTheDocument();
    expect(within(contextCard).getByText("현재 적용값: web · 출처: 스캔 대상")).toBeInTheDocument();
    expect(within(contextCard).getByLabelText("보호 기간 수정 값")).toHaveValue(10);
    expect(within(contextCard).getByLabelText("보호 기간 수정 값")).toHaveAttribute("placeholder", "미지정");
    expect(within(contextCard).getByLabelText("서비스 역할 수정 값")).toHaveValue("web");
    expect(within(contextCard).getByLabelText("서비스 역할 수정 값")).toHaveAttribute("placeholder", "미지정");
    await user.click(within(contextCard).getByRole("button", { name: "저장" }));
    expect(patchSpy).not.toHaveBeenCalled();
    expect(within(contextCard).queryByLabelText("민감도 수정 값")).not.toBeInTheDocument();
    expect(screen.getByText("Enriched CBOM")).toBeInTheDocument();
    expect(screen.queryByText("context.homepage.title")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "펼치기" }));
    expect(screen.getByText("context.homepage.title")).toBeInTheDocument();
    expect(screen.getAllByText("Customer Portal Login").length).toBeGreaterThanOrEqual(1);
  });

  it("sends only changed context fields from the inline form", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.assets, "get").mockResolvedValue(makeAssetDetail());
    vi.spyOn(services.performance, "history").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    vi.spyOn(services.jobs, "get").mockResolvedValue({
      id: 910,
      kind: "recompute",
      resource: { kind: "recompute", id: 910 },
      status: "COMPLETED",
      progress: null,
      started_at: null,
      cancel_requested_at: null,
      finished_at: "2026-05-01T00:00:00Z",
      result: { updated_scores_count: 1 },
      error: null
    });
    const patchSpy = vi.spyOn(services.assets, "patchContext").mockResolvedValue({
      asset_id: 84,
      applied_overrides: { sensitivity: "critical" },
      effective_context: {
        sensitivity: "critical",
        lifespan_years: 10,
        criticality: "high",
        exposure: "internal_network",
        service_role: "web"
      },
      context_override: {
        sensitivity: "critical",
        lifespan_years: null,
        criticality: null,
        exposure: null,
        service_role: null
      },
      context_sources: {
        sensitivity: "asset_override",
        lifespan_years: "target",
        criticality: "target",
        exposure: "target",
        service_role: "target"
      },
      recompute_job_id: 910
    });

    renderWithApp(<AssetDetailView snapshotId={2} assetId={84} />);

    await screen.findByRole("heading", { name: "asset detail certificate", level: 1 });
    await user.click(screen.getByRole("button", { name: /컨텍스트 수정/ }));
    await user.selectOptions(screen.getByLabelText("민감도 수정 값"), "critical");
    await user.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(patchSpy).toHaveBeenCalledWith(84, { sensitivity: "critical" }));
  });

  it("fills the inline context form from an AI recommendation without saving automatically", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.assets, "get").mockResolvedValue(makeAssetDetail());
    vi.spyOn(services.performance, "history").mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
    const patchSpy = vi.spyOn(services.assets, "patchContext");
    const suggestSpy = vi.spyOn(services.assets, "contextSuggestion").mockResolvedValue({
      asset_id: 84,
      prompt_version: "asset-context-suggestion-v1",
      recommended_context: {
        sensitivity: "critical",
        lifespan_years: 12,
        criticality: "critical",
        exposure: "public_internet",
        service_role: "customer-portal"
      },
      confidence: 0.87,
      rationale: "Customer portal certificate protects public long-lived customer sessions.",
      evidence: ["asset_name:customer portal certificate"],
      provider: { provider: "codex-cli", model: "gpt-test", usage: {} },
      fallback: { used: false, reason: null }
    });

    renderWithApp(<AssetDetailView snapshotId={2} assetId={84} />);

    await screen.findByRole("heading", { name: "asset detail certificate", level: 1 });
    await user.click(screen.getByRole("button", { name: /컨텍스트 수정/ }));
    await user.click(screen.getByRole("button", { name: "AI 추천" }));

    await waitFor(() => expect(suggestSpy).toHaveBeenCalledWith(84));
    expect(screen.getByLabelText("민감도 수정 값")).toHaveValue("critical");
    expect(screen.getByLabelText("중요도 수정 값")).toHaveValue("critical");
    expect(screen.getByLabelText("노출 범위 수정 값")).toHaveValue("public_internet");
    expect(screen.getByLabelText("보호 기간 수정 값")).toHaveValue(12);
    expect(screen.getByLabelText("서비스 역할 수정 값")).toHaveValue("customer-portal");
    expect(screen.getByText("신뢰도 87% · codex-cli")).toBeInTheDocument();
    expect(screen.getByText("Customer portal certificate protects public long-lived customer sessions.")).toBeInTheDocument();
    expect(patchSpy).not.toHaveBeenCalled();
  });
});

describe("SnapshotDiffView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders snapshot differences as side-by-side selectable asset tables", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.snapshots, "list").mockResolvedValue({ items: snapshots, total: 2, offset: 0, limit: 100 });
    vi.spyOn(services.snapshots, "diff").mockResolvedValue({
      snapshot_a: 1,
      snapshot_b: 2,
      added: [{ bom_ref: "cert:added", type: "certificate", name: "new cert" }],
      removed: [{ bom_ref: "cert:removed", type: "certificate", name: "old cert" }],
      modified: [
        {
          bom_ref: "cert:algo",
          type: "certificate",
          name: "same cert",
          field_changes: {
            algorithm: ["RSA-2048", "ML-DSA-65"],
            name: ["old name", "new name"]
          }
        }
      ],
      regressions: [
        {
          kind: "asset_removed",
          severity: "high",
          bom_ref: "cert:removed",
          asset_type: "certificate",
          message: "Asset is missing from the post-migration snapshot.",
          before: {
            bom_ref: "cert:removed",
            type: "certificate",
            name: "old cert",
            algorithm: "RSA-2048",
            algorithm_family: "RSA"
          },
          after: null
        }
      ],
      unchanged_count: 7
    });
    vi.spyOn(services.snapshots, "assets").mockImplementation(async (snapshotId) => ({
      items:
        snapshotId === 1
          ? [
              makeAsset({ id: 10, snapshot_id: 1, bom_ref: "cert:removed", name: "old cert", summary: { algorithm: "RSA-2048", algorithm_family: "RSA" } }),
              makeAsset({ id: 11, snapshot_id: 1, bom_ref: "cert:algo", name: "old name", summary: { algorithm: "RSA-2048", algorithm_family: "RSA" } }),
              makeAsset({ id: 12, snapshot_id: 1, bom_ref: "cert:same", name: "same cert", summary: { algorithm: "ECDSA", algorithm_family: "ECDSA" } })
            ]
          : [
              makeAsset({ id: 20, snapshot_id: 2, bom_ref: "cert:added", name: "new cert", summary: { algorithm: "ML-KEM-768", algorithm_family: "ML-KEM" } }),
              makeAsset({ id: 21, snapshot_id: 2, bom_ref: "cert:algo", name: "new name", summary: { algorithm: "ML-DSA-65", algorithm_family: "ML-DSA" } }),
              makeAsset({ id: 22, snapshot_id: 2, bom_ref: "cert:same", name: "same cert", summary: { algorithm: "ECDSA", algorithm_family: "ECDSA" } })
            ],
      total: 2,
      offset: 0,
      limit: 100
    }));

    renderWithApp(<SnapshotDiffView id={2} />);
    await screen.findByRole("option", { name: /#1/ });
    await user.selectOptions(await screen.findByRole("combobox"), "1");

    expect((await screen.findAllByText("스냅샷 #1")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("스냅샷 #2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("최신").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("cert:added")).toBeInTheDocument();
    expect(screen.getAllByText("cert:removed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("회귀 감지")).toBeInTheDocument();
    expect(screen.getByText("자산 누락")).toBeInTheDocument();
    expect(screen.getByText("전환 후 스냅샷에서 자산이 사라졌습니다.")).toBeInTheDocument();
    expect(screen.getAllByText("cert:algo").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("cert:same")).not.toBeInTheDocument();
    const getDiffRows = () => {
      const cards = Array.from(document.querySelectorAll<HTMLElement>(".snapshot-diff-table-card"));
      expect(cards).toHaveLength(2);
      return [
        Array.from(cards[0]!.querySelectorAll<HTMLTableRowElement>("tbody tr")),
        Array.from(cards[1]!.querySelectorAll<HTMLTableRowElement>("tbody tr"))
      ] as const;
    };
    const getBomRefCell = (row: HTMLTableRowElement) => row.querySelectorAll<HTMLTableCellElement>("td")[1]!;
    const [previousRows, currentRows] = getDiffRows();
    expect(previousRows).toHaveLength(3);
    expect(currentRows).toHaveLength(3);
    expect(getBomRefCell(previousRows[0]!)).toHaveTextContent("cert:algo");
    expect(getBomRefCell(currentRows[0]!)).toHaveTextContent("cert:algo");
    expect(getBomRefCell(previousRows[1]!)).toHaveTextContent("-");
    expect(getBomRefCell(currentRows[1]!)).toHaveTextContent("cert:added");
    expect(getBomRefCell(previousRows[2]!)).toHaveTextContent("cert:removed");
    expect(getBomRefCell(currentRows[2]!)).toHaveTextContent("-");
    expect(previousRows[1]).toHaveClass("is-clickable");
    const comparisonHeading = screen.getByText("선택 자산 비교");
    expect(comparisonHeading).toBeInTheDocument();
    expect(comparisonHeading.compareDocumentPosition(screen.getByRole("button", { name: "cert:removed" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText("RSA-2048").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("ML-DSA-65").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Raw Diff")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "cert:algo" })[0].closest("tr")).toHaveClass("is-selected");
    expect(screen.getByRole("button", { name: "cert:removed" }).closest(".snapshot-diff-table-card")).not.toBeNull();
    expect(screen.getByRole("checkbox", { name: "전체보기" }).closest(".snapshot-diff-controls")).not.toBeNull();

    await user.click(previousRows[1]!);
    expect(screen.getByText("스냅샷 #2에만 존재합니다.")).toBeInTheDocument();
    const [rowSelectedPreviousRows, rowSelectedCurrentRows] = getDiffRows();
    expect(rowSelectedPreviousRows[1]).toHaveClass("is-selected");
    expect(rowSelectedCurrentRows[1]).toHaveClass("is-selected");
    await user.click(screen.getByRole("button", { name: "cert:added" }));
    expect(screen.getByRole("button", { name: "cert:added" }).closest("tr")).toHaveClass("is-selected");

    await user.click(screen.getByRole("checkbox", { name: "전체보기" }));
    expect(screen.getAllByText("cert:same").length).toBeGreaterThanOrEqual(2);
    const [fullPreviousRows, fullCurrentRows] = getDiffRows();
    const sameRowIndex = fullPreviousRows.findIndex((row) => getBomRefCell(row).textContent?.includes("cert:same"));
    expect(sameRowIndex).toBeGreaterThanOrEqual(0);
    expect(getBomRefCell(fullCurrentRows[sameRowIndex]!)).toHaveTextContent("cert:same");
  });
});

function makeAsset(overrides: Partial<Schema<"AssetListItem">> & Pick<Schema<"AssetListItem">, "id" | "snapshot_id" | "bom_ref" | "name">) {
  return {
    asset_class: "crypto",
    asset_type: "certificate",
    target_id: null,
    target_label: null,
    summary: {},
    risk: null,
    ...overrides
  } satisfies Schema<"AssetListItem">;
}

function makeAssetDetail(overrides: Partial<Schema<"AssetDetail">> = {}) {
  return {
    id: 84,
    snapshot_id: 2,
    bom_ref: "tls:web:detail",
    asset_class: "crypto",
    asset_type: "certificate",
    name: "asset detail certificate",
    crypto_properties: { algorithm: "RSA-2048" },
    properties: {},
    discovered_at: "2026-05-01T00:00:00Z",
    target: { id: 10, host: "web.testbed.local", port: 443 },
    effective_context: {
      sensitivity: "high",
      lifespan_years: 10,
      criticality: "high",
      exposure: "internal_network",
      service_role: "web"
    },
    context_override: {
      sensitivity: null,
      lifespan_years: null,
      criticality: null,
      exposure: null,
      service_role: null
    },
    context_sources: {
      sensitivity: "target",
      lifespan_years: "target",
      criticality: "target",
      exposure: "target",
      service_role: "target"
    },
    risk: null,
    qualitative: null,
    dependencies: { dependsOn: [], dependedBy: [] },
    history: [],
    enriched_cbom_component: {
      type: "crypto-asset",
      "bom-ref": "tls:web:detail",
      name: "asset detail certificate",
      cryptoProperties: {
        assetType: "certificate",
        algorithm: "RSA-2048",
        algorithmFamily: "RSA"
      },
      properties: [
        { name: "context.homepage.source", value: "homepage" },
        { name: "context.homepage.title", value: "Customer Portal Login" },
        { name: "risk.tier", value: "HIGH" }
      ]
    },
    ...overrides
  } satisfies Schema<"AssetDetail">;
}
