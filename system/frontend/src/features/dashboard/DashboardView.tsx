import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Plus } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import { StatusBadge } from "../../components/common/Badges";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { BarChartCard, DonutChartCard, TrendChartCard } from "../../components/charts/ChartCards";
import { MetricCard } from "../../components/charts/MetricCard";
import { NetworkExposureGraphViz } from "../../components/graph/NetworkExposureGraphViz";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { DataTable } from "../../components/ui/table";
import { assetTypeLabel, contextValueLabel, jobKindLabel, riskTierLabel } from "../../domain/displayLabels";
import type { NetworkExposureNode } from "../../domain/networkExposureGraph";
import { buildNetworkExposureGraph } from "../../domain/networkExposureGraph";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";
import { getLatestSnapshotId } from "../snapshots/GlobalSnapshotSelector";
import { useSelectedSnapshot } from "../snapshots/useSelectedSnapshot";

function objectToChartData(value: Record<string, number> | undefined, labeler: (name: string) => string = (name) => name) {
  return Object.entries(value ?? {}).map(([name, count]) => ({ name: labeler(name), value: count }));
}

const GRAPH_REFRESH_MS = 15_000;
const GRAPH_ASSET_QUERY = { limit: 100, sort: "-risk_score" } as const;
const GRAPH_TARGET_QUERY = { limit: 100 } as const;

type HomepageContextInference = {
  target_id: number;
  target_label: string;
  service_role?: string | null;
  sensitivity?: string | null;
  criticality?: string | null;
  exposure?: string | null;
  lifespan_years?: number | null;
  confidence?: number | null;
  title?: string | null;
  description?: string | null;
  signals?: string[];
  url?: string | null;
};

export function DashboardView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSelectedSnapshotId = useSnapshotSelectionStore((state) => state.setSelectedSnapshotId);
  const { snapshotItems, selectedSnapshotId } = useSelectedSnapshot();
  const latestSnapshotId = useMemo(() => getLatestSnapshotId(snapshotItems), [snapshotItems]);
  const dashboardSnapshotId = latestSnapshotId ?? undefined;

  useEffect(() => {
    if (latestSnapshotId && selectedSnapshotId !== latestSnapshotId) {
      setSelectedSnapshotId(latestSnapshotId);
    }
  }, [latestSnapshotId, selectedSnapshotId, setSelectedSnapshotId]);

  const summary = useQuery({
    queryKey: queryKeys.dashboard.summary(dashboardSnapshotId),
    queryFn: () => services.dashboard.summary(dashboardSnapshotId),
    refetchInterval: GRAPH_REFRESH_MS
  });
  const graphSnapshotId = summary.data?.snapshot?.id;
  const graphAssets = useQuery({
    queryKey: queryKeys.snapshots.assets(graphSnapshotId ?? 0, GRAPH_ASSET_QUERY),
    queryFn: () => services.snapshots.assets(graphSnapshotId!, GRAPH_ASSET_QUERY),
    enabled: Boolean(graphSnapshotId),
    refetchInterval: GRAPH_REFRESH_MS
  });
  const graphTargets = useQuery({
    queryKey: queryKeys.targets.list(GRAPH_TARGET_QUERY),
    queryFn: () => services.targets.list(GRAPH_TARGET_QUERY),
    enabled: Boolean(graphSnapshotId),
    refetchInterval: GRAPH_REFRESH_MS * 2
  });

  const tierData = useMemo(() => objectToChartData(summary.data?.by_tier, riskTierLabel), [summary.data?.by_tier]);
  const assetTypeData = useMemo(() => objectToChartData(summary.data?.by_asset_type, assetTypeLabel), [summary.data?.by_asset_type]);
  const algorithmData = useMemo(() => objectToChartData(summary.data?.by_algorithm_family), [summary.data?.by_algorithm_family]);
  const quantumData = useMemo(
    () => objectToChartData(summary.data?.quantum_vulnerable_ratio, quantumStatusLabel),
    [summary.data?.quantum_vulnerable_ratio]
  );
  const trend = useMemo(
    () =>
      (summary.data?.trend ?? []).map((item) => ({
        name: `#${item.snapshot_id}`,
        critical: item.critical_count,
        total: item.total_count
      })),
    [summary.data?.trend]
  );
  const contextInferences = useMemo(() => dashboardContextInferences(summary.data), [summary.data]);
  const exposureGraph = useMemo(
    () => buildNetworkExposureGraph(graphAssets.data?.items ?? [], graphTargets.data?.items ?? []),
    [graphAssets.data?.items, graphTargets.data?.items]
  );
  const seedDemo = useMutation({
    mutationFn: () => services.dashboard.seedDemo({ reset: true }),
    onSuccess: async (result) => {
      if (result.latest_snapshot_id) {
        setSelectedSnapshotId(result.latest_snapshot_id);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.targets.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.agents.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.risk.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.performance.all })
      ]);
      toast.success(`시연 데이터 ${formatNumber(result.asset_count)}개 자산을 로드했습니다.`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "시연 데이터 로드에 실패했습니다.");
    }
  });

  function openGraphNode(node: NetworkExposureNode) {
    if (node.kind === "asset" && node.refId) {
      navigate(graphSnapshotId ? `/snapshots/${graphSnapshotId}/assets/${node.refId}` : "/snapshots");
      return;
    }
    if ((node.kind === "target" || node.kind === "endpoint") && node.refId) {
      navigate(`/targets/${node.refId}`);
      return;
    }
    if (node.kind === "finding" && graphSnapshotId) {
      navigate(`/snapshots?tier=${node.riskTier ?? ""}`);
    }
  }

  if (summary.isLoading) {
    return <LoadingState />;
  }

  if (summary.isError) {
    return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />;
  }

  if (!summary.data?.snapshot) {
    return (
      <Section>
        <PageHeader
          title="대시보드"
          description="전체 PQC 위험 현황을 한 화면에서 확인합니다."
          actions={<SeedDemoButton isPending={seedDemo.isPending} onClick={() => seedDemo.mutate()} />}
        />
        <EmptyState
          title="아직 스냅샷이 없습니다"
          description="탐색 대상에서 후보 엔드포인트를 찾으면 스캔 대상이 자동 등록되고, 이후 스캔을 실행하면 대시보드가 채워집니다."
          action={
            <div className="inline-actions">
              <SeedDemoButton isPending={seedDemo.isPending} onClick={() => seedDemo.mutate()} />
              <Button type="button" variant="primary" onClick={() => navigate("/discoveries/new")}>
                탐색 대상 추가
              </Button>
              <Button type="button" onClick={() => navigate("/targets")}>
                스캔 대상 추가
              </Button>
            </div>
          }
        />
      </Section>
    );
  }

  const dashboardSnapshot = summary.data.snapshot;
  const discoveredAssetsKpi = summary.data.kpis.discovered_crypto_assets_per_scan;
  const vulnerableAssetsKpi = summary.data.kpis.quantum_vulnerable_assets_per_scan;
  const expiringCertificatesKpi = summary.data.kpis.expiring_certificates_90d_per_scan;
  const dormantPrivateKeysKpi = summary.data.kpis.dormant_private_keys_per_scan;
  const automatedRuntimeKpi = summary.data.kpis.automated_inventory_runtime_minutes_per_scan;
  const pipelineRuntimeKpi = summary.data.kpis.full_pipeline_runtime_minutes;

  return (
    <Section>
      <PageHeader
        title="대시보드"
        eyebrow="대시보드"
        actions={
          <div className="inline-actions">
            <SeedDemoButton isPending={seedDemo.isPending} onClick={() => seedDemo.mutate()} />
            <Button type="button" variant="primary" onClick={() => navigate("/scans/new")}>
              <Plus size={15} />새 스캔
            </Button>
          </div>
        }
      />

      <div className="content-grid content-grid--4">
        <MetricCard
          label="스캔당 발견 자산"
          value={formatNumber(discoveredAssetsKpi.value)}
          meta={discoveredAssetsKpi.scan_job_id ? `스캔 #${discoveredAssetsKpi.scan_job_id}` : "스냅샷 기준"}
          onClick={() => navigate("/snapshots")}
        />
        <MetricCard label="자산수" value={formatNumber(dashboardSnapshot.asset_count)} onClick={() => navigate("/snapshots")} />
        <MetricCard
          label="치명 위험"
          value={formatNumber(summary.data.by_tier.CRITICAL ?? 0)}
          onClick={() => navigate("/snapshots?tier=CRITICAL")}
        />
        <MetricCard
          label="양자취약"
          value={formatNumber(vulnerableAssetsKpi.value)}
          meta={`안전 ${summary.data.quantum_vulnerable_ratio.safe}`}
        />
        <MetricCard
          label="만료 임박 인증서"
          value={formatNumber(expiringCertificatesKpi.value)}
          meta="90일 이내"
          onClick={() => navigate("/snapshots?asset_type=certificate")}
        />
        <MetricCard
          label="잠든 개인키"
          value={formatNumber(dormantPrivateKeysKpi.value)}
          meta="미사용 파일"
          onClick={() => navigate("/snapshots")}
        />
        <MetricCard
          label="자동화 실행 시간"
          value={`${formatNumber(automatedRuntimeKpi.value)}분`}
          meta={automatedRuntimeKpi.scan_job_id ? `스캔 #${automatedRuntimeKpi.scan_job_id}` : "스냅샷 기준"}
          onClick={() => navigate("/scans")}
        />
        <MetricCard
          label="전체 파이프라인"
          value={`${formatNumber(pipelineRuntimeKpi.value)}분`}
          meta="10분 이내"
          onClick={() => navigate("/scans")}
        />
        <MetricCard
          label="에이전트"
          value={`${summary.data.agents_status.active}/${summary.data.agents_status.total}`}
          meta={`지연 ${summary.data.agents_status.stale}`}
          onClick={() => navigate("/agents")}
        />
      </div>

      <NetworkExposureGraphViz
        graph={exposureGraph}
        isLoading={graphAssets.isLoading || graphTargets.isLoading}
        isFetching={graphAssets.isFetching || graphTargets.isFetching || summary.isFetching}
        error={graphAssets.error ?? graphTargets.error}
        updatedAt={Math.max(graphAssets.dataUpdatedAt, graphTargets.dataUpdatedAt, summary.dataUpdatedAt)}
        onRetry={() => {
          void graphAssets.refetch();
          void graphTargets.refetch();
          void summary.refetch();
        }}
        onOpenNode={openGraphNode}
      />

      <div className="dashboard-chart-grid">
        <DonutChartCard title="위험도 등급 분포" data={tierData} />
        <DonutChartCard title="자산 타입 분포" data={assetTypeData} />
        <BarChartCard title="알고리즘 패밀리 분포" data={algorithmData} />
        <DonutChartCard title="양자취약/안전 비율" data={quantumData} />
      </div>

      <div className="dashboard-secondary-grid">
        <Card>
          <CardHeader>
            <CardTitle>홈페이지 추론 컨텍스트</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              items={contextInferences}
              getRowKey={(item) => item.target_id}
              empty={<EmptyState title="홈페이지 추론 결과가 없습니다" description="웹 서비스 스캔 시 공개 홈페이지의 제목과 본문 신호로 운영 맥락을 추정합니다." />}
              columns={[
                { key: "target", header: "대상", render: (item) => <button className="link-button" onClick={() => navigate(`/targets/${item.target_id}`)}>{item.target_label}</button> },
                { key: "title", header: "홈페이지", render: (item) => item.title || "-" },
                { key: "role", header: "역할", render: (item) => contextValueLabel("service_role", item.service_role) },
                { key: "exposure", header: "노출", render: (item) => contextValueLabel("exposure", item.exposure) },
                { key: "confidence", header: "신뢰도", align: "right", render: (item) => formatConfidence(item.confidence) }
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>최근 스캔 실행</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              items={summary.data.recent_jobs}
              getRowKey={(job) => job.id}
              columns={[
                { key: "id", header: "작업", render: (job) => <button className="link-button" onClick={() => navigate(`/scans/${job.id}`)}>#{job.id}</button> },
                { key: "kind", header: "종류", render: (job) => jobKindLabel(job.kind) },
                { key: "status", header: "상태", render: (job) => <StatusBadge status={job.status} /> },
                { key: "started", header: "시작", render: (job) => formatDateTime(job.started_at) },
                { key: "finished", header: "종료", render: (job) => formatDateTime(job.finished_at) }
              ]}
            />
          </CardContent>
        </Card>
        <TrendChartCard data={trend} />
      </div>
    </Section>
  );
}

function SeedDemoButton({ isPending, onClick }: { isPending: boolean; onClick: () => void }) {
  return (
    <Button type="button" onClick={onClick} disabled={isPending}>
      <Database size={15} />
      {isPending ? "로드 중" : "시연 데이터 로드"}
    </Button>
  );
}

function quantumStatusLabel(name: string) {
  const labels: Record<string, string> = {
    vulnerable: "양자취약",
    safe: "안전"
  };
  return labels[name] ?? name;
}

function dashboardContextInferences(summary?: SchemaWithContextInferences | null): HomepageContextInference[] {
  const value = summary?.context_inferences;
  return Array.isArray(value) ? value : [];
}

function formatConfidence(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

type SchemaWithContextInferences = {
  context_inferences?: HomepageContextInference[];
};
