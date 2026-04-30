import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

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
import type { NetworkExposureNode } from "../../domain/networkExposureGraph";
import { buildNetworkExposureGraph } from "../../domain/networkExposureGraph";
import { formatDateTime, formatNumber } from "../../lib/format";
import { useSelectedSnapshot } from "../snapshots/useSelectedSnapshot";

function objectToChartData(value: Record<string, number> | undefined) {
  return Object.entries(value ?? {}).map(([name, count]) => ({ name, value: count }));
}

const GRAPH_REFRESH_MS = 15_000;
const GRAPH_ASSET_QUERY = { limit: 100, sort: "-risk_score" } as const;
const GRAPH_TARGET_QUERY = { limit: 100 } as const;

export function DashboardView() {
  const navigate = useNavigate();
  const { selectedSnapshotId } = useSelectedSnapshot();
  const summary = useQuery({
    queryKey: queryKeys.dashboard.summary(selectedSnapshotId ?? undefined),
    queryFn: () => services.dashboard.summary(selectedSnapshotId ?? undefined),
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

  const tierData = useMemo(() => objectToChartData(summary.data?.by_tier), [summary.data?.by_tier]);
  const assetTypeData = useMemo(() => objectToChartData(summary.data?.by_asset_type), [summary.data?.by_asset_type]);
  const algorithmData = useMemo(() => objectToChartData(summary.data?.by_algorithm_family), [summary.data?.by_algorithm_family]);
  const quantumData = useMemo(
    () => objectToChartData(summary.data?.quantum_vulnerable_ratio),
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
  const exposureGraph = useMemo(
    () => buildNetworkExposureGraph(graphAssets.data?.items ?? [], graphTargets.data?.items ?? []),
    [graphAssets.data?.items, graphTargets.data?.items]
  );

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
        <PageHeader title="대시보드" description="전체 PQC 위험 현황을 한 화면에서 확인합니다." />
        <EmptyState
          title="아직 스냅샷이 없습니다"
          description="CIDR 디스커버리로 후보 엔드포인트를 찾거나 스캔 대상을 수동으로 추가한 뒤 스캔을 실행하면 대시보드가 채워집니다."
          action={
            <div className="inline-actions">
              <Button type="button" variant="primary" onClick={() => navigate("/discoveries/new")}>
                디스커버리 시작
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

  return (
    <Section>
      <PageHeader
        title="대시보드"
        eyebrow="DASHBOARD"
        actions={
          <Button type="button" variant="primary" onClick={() => navigate("/scans/new")}>
            <Plus size={15} />새 스캔
          </Button>
        }
      />

      <div className="content-grid content-grid--4">
        <MetricCard label="자산수" value={formatNumber(dashboardSnapshot.asset_count)} onClick={() => navigate("/snapshots")} />
        <MetricCard
          label="Critical"
          value={formatNumber(summary.data.by_tier.CRITICAL ?? 0)}
          onClick={() => navigate("/snapshots?tier=CRITICAL")}
        />
        <MetricCard
          label="양자취약"
          value={formatNumber(summary.data.quantum_vulnerable_ratio.vulnerable)}
          meta={`Safe ${summary.data.quantum_vulnerable_ratio.safe}`}
        />
        <MetricCard
          label="Agents"
          value={`${summary.data.agents_status.active}/${summary.data.agents_status.total}`}
          meta={`stale ${summary.data.agents_status.stale}`}
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
            <CardTitle>최근 스캔 실행</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              items={summary.data.recent_jobs}
              getRowKey={(job) => job.id}
              columns={[
                { key: "id", header: "Job", render: (job) => <button className="link-button" onClick={() => navigate(`/scans/${job.id}`)}>#{job.id}</button> },
                { key: "kind", header: "Kind", render: (job) => job.kind },
                { key: "status", header: "Status", render: (job) => <StatusBadge status={job.status} /> },
                { key: "started", header: "Started", render: (job) => formatDateTime(job.started_at) },
                { key: "finished", header: "Finished", render: (job) => formatDateTime(job.finished_at) }
              ]}
            />
          </CardContent>
        </Card>
        <TrendChartCard data={trend} />
      </div>
    </Section>
  );
}
