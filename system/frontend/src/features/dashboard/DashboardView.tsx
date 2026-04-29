import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import { StatusBadge } from "../../components/common/Badges";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { BarChartCard, DonutChartCard, TrendChartCard } from "../../components/charts/ChartCards";
import { MetricCard } from "../../components/charts/MetricCard";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { SnapshotSummaryModel } from "../../domain/models";
import { formatDateTime, formatNumber } from "../../lib/format";

function objectToChartData(value: Record<string, number> | undefined) {
  return Object.entries(value ?? {}).map(([name, count]) => ({ name, value: count }));
}

export function DashboardView() {
  const navigate = useNavigate();
  const [snapshotId, setSnapshotId] = useState<number | undefined>();
  const snapshots = useQuery({
    queryKey: queryKeys.snapshots.all,
    queryFn: () => services.snapshots.list()
  });
  const summary = useQuery({
    queryKey: queryKeys.dashboard.summary(snapshotId),
    queryFn: () => services.dashboard.summary(snapshotId)
  });

  const selectedSnapshot = summary.data?.snapshot;
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
          description="타겟을 등록하거나 네트워크 디스커버리를 시작한 뒤 스캔을 실행하면 대시보드가 채워집니다."
          action={
            <div className="inline-actions">
              <Button type="button" variant="primary" onClick={() => navigate("/discoveries/new")}>
                디스커버리 시작
              </Button>
              <Button type="button" onClick={() => navigate("/targets")}>
                타겟 등록
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
        description={new SnapshotSummaryModel(dashboardSnapshot).label()}
        actions={
          <>
            <Select aria-label="Dashboard snapshot selector" value={snapshotId ?? ""} onChange={(event) => setSnapshotId(event.target.value ? Number(event.target.value) : undefined)}>
              <option value="">최신 스냅샷</option>
              {(snapshots.data?.items ?? []).map((snapshot) => (
                <option key={snapshot.id} value={snapshot.id}>
                  #{snapshot.id} · {formatDateTime(snapshot.created_at)}
                </option>
              ))}
            </Select>
            <Button type="button" variant="primary" onClick={() => navigate("/scans/new")}>
              <Plus size={15} />새 스캔
            </Button>
          </>
        }
      />

      <div className="content-grid content-grid--4">
        <MetricCard label="자산수" value={formatNumber(dashboardSnapshot.asset_count)} onClick={() => navigate(`/snapshots/${dashboardSnapshot.id}`)} />
        <MetricCard
          label="Critical"
          value={formatNumber(summary.data.by_tier.CRITICAL ?? 0)}
          onClick={() => navigate(`/snapshots/${dashboardSnapshot.id}?tier=CRITICAL`)}
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

      <div className="content-grid">
        <DonutChartCard title="위험도 등급 분포" data={tierData} />
        <DonutChartCard title="자산 타입 분포" data={assetTypeData} />
        <BarChartCard title="알고리즘 패밀리 분포" data={algorithmData} />
        <DonutChartCard title="양자취약/안전 비율" data={quantumData} />
        <div className="is-wide">
          <TrendChartCard data={trend} />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>최근 Scan Jobs</CardTitle>
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
    </Section>
  );
}
