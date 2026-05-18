import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { ChartCard } from "../../components/charts/ChartCards";
import { MetricCard } from "../../components/charts/MetricCard";
import { chartPalette, chartTheme } from "../../components/charts/chartTheme";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Field, FieldLabel, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { performanceStatusLabel, profileLabel } from "../../domain/displayLabels";
import { formatDateTime, formatNumber } from "../../lib/format";

type PerformanceRun = Schema<"PerformanceEvaluationRun">;
type PerformanceResult = Schema<"AssetPerformanceResult">;
type PerformanceProfile = Schema<"PerformanceRunProfile">;
type FailurePath = NonNullable<Schema<"PerformanceRunSummary">["failure_paths"]>[number];

const profiles: PerformanceProfile[] = ["smoke", "baseline", "canary", "stress"];

export function PerformanceEvaluationView({ snapshotId }: { snapshotId: number }) {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const profileParam = searchParams.get("profile") ?? "";
  const selectedRunId = searchParams.get("run") ? Number(searchParams.get("run")) : undefined;
  const profile = profiles.includes(profileParam as PerformanceProfile) ? (profileParam as PerformanceProfile) : "";
  const filters = useMemo(() => ({ profile: profile || undefined }), [profile]);
  const runs = useQuery({
    queryKey: queryKeys.performance.runs(snapshotId, filters),
    queryFn: () => services.performance.listRuns(snapshotId, filters),
    refetchInterval: (query) => (pageHasActiveRun(query.state.data?.items) ? 2_000 : false)
  });
  const runItems = runs.data?.items ?? [];
  const activeRunId = selectedRunId && runItems.some((run) => run.id === selectedRunId) ? selectedRunId : runItems[0]?.id;
  const detail = useQuery({
    queryKey: queryKeys.performance.detail(snapshotId, activeRunId ?? 0),
    queryFn: () => services.performance.getRun(snapshotId, activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => (isActiveStatus(query.state.data?.status) ? 2_000 : false)
  });
  const startRun = useMutation({
    mutationFn: () =>
      services.performance.createRun(snapshotId, {
        trigger: "manual",
        profile: profile || "smoke",
        auto_start: true,
        environment: { source: "web" }
      }),
    onSuccess: async (run) => {
      const next = new URLSearchParams(searchParams);
      if (profile) {
        next.set("profile", profile);
      }
      next.set("run", String(run.id));
      setSearchParams(next);
      await queryClient.invalidateQueries({ queryKey: queryKeys.performance.runsPrefix(snapshotId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.performance.detail(snapshotId, run.id) });
      toast.success(`가용성 검사 #${run.id} 실행을 시작했습니다.`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "가용성 검사 실행 실패")
  });

  function setFilter(name: "profile" | "run", value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(name, value);
    } else {
      next.delete(name);
    }
    if (name === "profile") {
      next.delete("run");
    }
    setSearchParams(next);
  }

  return (
    <Section>
      <PageHeader
        title={`스냅샷 #${snapshotId} 가용성 검사`}
        description="가용성 검사 실행과 자산별 측정 결과를 조회합니다."
        actions={
          <Button type="button" variant="primary" disabled={startRun.isPending} onClick={() => startRun.mutate()}>
            <Play size={15} />가용성 검사 실행
          </Button>
        }
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Field className="field-inline">
                <FieldLabel>프로파일</FieldLabel>
                <Select aria-label="가용성 검사 프로파일 필터" value={profile} onChange={(event) => setFilter("profile", event.target.value)}>
                  <option value="">전체 프로파일</option>
                  {profiles.map((item) => (
                    <option key={item} value={item}>{profileLabel(item)}</option>
                  ))}
                </Select>
              </Field>
              <Field className="field-inline">
                <FieldLabel>실행</FieldLabel>
                <Select
                  aria-label="가용성 검사 실행 선택"
                  disabled={runItems.length === 0}
                  value={activeRunId ?? ""}
                  onChange={(event) => setFilter("run", event.target.value)}
                >
                  {runItems.length === 0 ? <option value="">실행 없음</option> : null}
                  {runItems.map((run) => (
                    <option key={run.id} value={run.id}>
                      #{run.id} · {triggerLabel(run.trigger)} · {formatDateTime(run.created_at)}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          </div>
        </CardContent>
      </Card>
      {runs.isLoading ? <LoadingState /> : null}
      {runs.isError ? <ErrorState error={runs.error} onRetry={() => void runs.refetch()} /> : null}
      {runs.data && runItems.length === 0 ? (
        <EmptyState title="가용성 검사 실행이 없습니다" description="실행 버튼을 누르면 현재 스냅샷의 스캔 대상 기준으로 서비스 연결 가능 여부를 검사합니다." />
      ) : null}
      {detail.isLoading && activeRunId ? <LoadingState /> : null}
      {detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {detail.data ? <PerformanceRunDetail run={detail.data} /> : null}
    </Section>
  );
}

function pageHasActiveRun(items?: PerformanceRun[]) {
  return Boolean(items?.some((run) => isActiveStatus(run.status)));
}

function isActiveStatus(status?: string | null) {
  return status === "PENDING" || status === "RUNNING";
}

function PerformanceRunDetail({ run }: { run: Schema<"PerformanceEvaluationRunDetail"> }) {
  const summary = run.summary;
  const failurePaths = summary.failure_paths ?? [];
  const warnFailCount = (summary.by_status.WARN ?? 0) + (summary.by_status.FAIL ?? 0) + (summary.by_status.ERROR ?? 0);
  const successRate = averageNumber(run.results.map((result) => successRateMetric(result)));
  const clientCompatibilityRate = compatibilitySuccessRate(summary.client_compatibility);
  const handshakeComparison = summary.latency_comparison?.handshake_ms;
  const throughputComparison = primaryThroughputComparison(summary.throughput_comparison);
  const throughputChartData = run.results
    .map((result) => ({
      name: shortAssetLabel(result.bom_ref),
      baseline: baselineThroughputMetric(result),
      current: throughputMetric(result)
    }))
    .filter((item) => typeof item.baseline === "number" || typeof item.current === "number");
  const protocolCount = new Set(run.results.map((result) => result.protocol || metricProtocol(result))).size;
  return (
    <div className="section-stack">
      <div className="content-grid content-grid--4">
        <MetricCard label="전체 상태" value={performanceStatusLabel(summary.overall_status)} />
        <MetricCard label="결과 수" value={formatNumber(summary.total_results)} />
        <MetricCard label="경고/실패" value={formatNumber(warnFailCount)} />
        <MetricCard label="성공률" value={formatPercent(successRate)} />
        <MetricCard label="클라이언트 호환성" value={formatPercent(clientCompatibilityRate)} />
        <MetricCard label="핸드셰이크 전/후" value={formatLatencyComparison(handshakeComparison)} />
        <MetricCard label="처리량 전/후" value={formatThroughputComparison(throughputComparison)} />
        <MetricCard label="프로토콜" value={formatNumber(protocolCount)} />
        <MetricCard label="기준 스냅샷" value={run.baseline_snapshot_id ? `#${run.baseline_snapshot_id}` : "-"} />
        <MetricCard label="전환 후 스냅샷" value={run.post_migration_snapshot_id ? `#${run.post_migration_snapshot_id}` : "-"} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>실행 메타데이터</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="detail-list">
            <div><dt>상태</dt><dd><PerformanceStatusBadge status={run.status} /></dd></div>
            <div><dt>트리거</dt><dd>{triggerLabel(run.trigger)}</dd></div>
            <div><dt>프로파일</dt><dd>{profileLabel(run.profile)}</dd></div>
            <div><dt>시작</dt><dd>{formatDateTime(run.started_at)}</dd></div>
            <div><dt>완료</dt><dd>{formatDateTime(run.completed_at)}</dd></div>
          </dl>
        </CardContent>
      </Card>
      {throughputChartData.length > 0 ? (
        <ChartCard title="자산별 처리량 비교">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={throughputChartData} margin={{ left: 10, right: 16, bottom: 8 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tickMargin={8} />
              <YAxis unit=" req/s" width={82} />
              <Tooltip formatter={(value) => formatRps(typeof value === "number" ? value : undefined)} />
              <Bar dataKey="baseline" name="기준" fill={chartPalette[5]} radius={[chartTheme.radius, chartTheme.radius, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="current" name="현재" fill={chartPalette[3]} radius={[chartTheme.radius, chartTheme.radius, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>실패 경로 보고</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            items={failurePaths}
            getRowKey={(item, index) => `${item.protocol}:${item.client_profile}:${item.response_code}:${item.failure_reason}:${index}`}
            empty={<EmptyState title="보고할 실패 경로가 없습니다" />}
            columns={[
              { key: "status", header: "상태", render: (item) => <PerformanceStatusBadge status={item.status} /> },
              { key: "protocol", header: "프로토콜", render: (item) => item.protocol || "-" },
              { key: "client", header: "클라이언트", render: (item) => item.client_profile || "-" },
              { key: "response", header: "응답 코드", render: (item) => item.response_code || "-" },
              { key: "reason", header: "실패 사유", render: (item) => item.failure_reason || "-" },
              { key: "assets", header: "영향 자산", render: (item) => formatFailurePathAssets(item) },
              { key: "count", header: "건수", align: "right", render: (item) => formatNumber(item.count) }
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>자산별 결과</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            items={run.results}
            getRowKey={(item) => item.id}
            empty={<EmptyState title="자산별 가용성 검사 결과가 없습니다" />}
            columns={[
              { key: "asset", header: "자산", render: (item) => <span className="mono">{item.bom_ref}</span> },
              { key: "target", header: "스캔 대상", render: (item) => item.target_label ?? "-" },
              { key: "protocol", header: "프로토콜", render: (item) => item.protocol || metricProtocol(item) },
              { key: "status", header: "상태", render: (item) => <PerformanceStatusBadge status={item.status} /> },
              { key: "compatibility", header: "호환성", render: (item) => <PerformanceStatusBadge status={item.compatibility_status} /> },
              { key: "algorithm", header: "협상 알고리즘", render: (item) => item.negotiated_algorithm || "-" },
              { key: "response", header: "응답 코드", render: (item) => item.response_code || metricText(item, "response_code") || "-" },
              { key: "failureReason", header: "실패 사유", render: (item) => item.failure_reason || metricText(item, "failure_reason") || "-" },
              { key: "success", header: "성공률", align: "right", render: (item) => formatPercent(successRateMetric(item)) },
              { key: "clientCompatibility", header: "클라이언트 호환성", render: (item) => formatClientCompatibility(item) },
              { key: "baselineHandshake", header: "기준 p95", align: "right", render: (item) => formatMs(baselineMetricP95(item, "handshake_ms")) },
              { key: "handshake", header: "핸드셰이크/협상 p95", align: "right", render: (item) => formatMs(metricP95(item, "handshake_ms")) },
              { key: "ttfb", header: "TTFB p95", align: "right", render: (item) => formatMs(metricP95(item, "ttfb_ms")) },
              { key: "baselineThroughput", header: "기준 처리량", align: "right", render: (item) => formatRps(baselineThroughputMetric(item)) },
              { key: "throughput", header: "처리량", align: "right", render: (item) => formatRps(throughputMetric(item)) },
              { key: "failure", header: "실패율", align: "right", render: (item) => formatPercent(numberMetric(item, "failure_rate")) },
              { key: "delta", header: "핸드셰이크 변화율", align: "right", render: (item) => formatSignedPercent(item.deltas.handshake_p95_percent) },
              { key: "throughputDelta", header: "처리량 변화율", align: "right", render: (item) => formatSignedPercent(throughputDelta(item)) },
              { key: "recommendation", header: "권고", render: (item) => item.recommendation }
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function PerformanceStatusBadge({ status }: { status?: string | null }) {
  const tone = status === "PASS" || status === "COMPLETED" ? "green" : status === "WARN" || status === "RUNNING" ? "yellow" : status === "FAIL" || status === "ERROR" || status === "FAILED" ? "red" : "neutral";
  return <Badge tone={tone}>{performanceStatusLabel(status)}</Badge>;
}

function triggerLabel(trigger: string) {
  const labels: Record<string, string> = {
    manual: "수동",
    agent_upload: "에이전트 업로드",
    scheduled: "예약",
    discovery: "탐색 후 자동",
    migration_validation: "마이그레이션 검증"
  };
  return labels[trigger] ?? trigger;
}

function metricP95(result: PerformanceResult, key: "tcp_connect_ms" | "handshake_ms" | "ttfb_ms" | "total_request_ms") {
  const metric = result.metrics[key];
  if (metric && typeof metric === "object" && "p95" in metric) {
    return metric.p95;
  }
  return undefined;
}

function baselineMetricP95(result: PerformanceResult, key: "tcp_connect_ms" | "handshake_ms" | "ttfb_ms" | "total_request_ms") {
  const baseline = result.metrics.baseline_metrics;
  if (!baseline || typeof baseline !== "object" || Array.isArray(baseline)) {
    return undefined;
  }
  const metric = (baseline as Record<string, unknown>)[key];
  if (metric && typeof metric === "object" && "p95" in metric && typeof metric.p95 === "number") {
    return metric.p95;
  }
  return undefined;
}

function numberMetric(
  result: PerformanceResult,
  key:
    | "failure_rate"
    | "timeout_rate"
    | "session_resumption_rate"
    | "availability_success_rate"
    | "handshake_success_rate"
    | "negotiation_success_rate"
    | "throughput_rps"
    | "requests_per_second"
    | "connections_per_second"
) {
  const value = result.metrics[key];
  return typeof value === "number" ? value : undefined;
}

function successRateMetric(result: PerformanceResult) {
  return numberMetric(result, "availability_success_rate") ?? numberMetric(result, "handshake_success_rate") ?? numberMetric(result, "negotiation_success_rate");
}

function compatibilitySuccessRate(summary?: Schema<"PerformanceRunSummary">["client_compatibility"]) {
  const total = summary?.total_checks;
  if (!total) {
    return undefined;
  }
  return (summary.by_status.PASS ?? 0) / total;
}

function clientCompatibilityChecks(result: PerformanceResult) {
  return Array.isArray(result.metrics.client_compatibility) ? result.metrics.client_compatibility : [];
}

function formatClientCompatibility(result: PerformanceResult) {
  const checks = clientCompatibilityChecks(result);
  if (checks.length === 0) {
    return "-";
  }
  return checks.map((check) => `${check.profile}: ${performanceStatusLabel(check.status)}`).join(", ");
}

function formatFailurePathAssets(path: FailurePath) {
  return path.asset_refs.length > 0 ? path.asset_refs.join(", ") : "-";
}

function throughputMetric(result: PerformanceResult) {
  return numberMetric(result, "throughput_rps") ?? numberMetric(result, "requests_per_second") ?? numberMetric(result, "connections_per_second");
}

function throughputDelta(result: PerformanceResult) {
  return result.deltas.throughput_rps_percent ?? result.deltas.requests_per_second_percent ?? result.deltas.connections_per_second_percent;
}

function baselineThroughputMetric(result: PerformanceResult) {
  const baseline = result.metrics.baseline_metrics;
  if (!baseline || typeof baseline !== "object" || Array.isArray(baseline)) {
    return undefined;
  }
  const metrics = baseline as Record<string, unknown>;
  const value = metrics.throughput_rps ?? metrics.requests_per_second ?? metrics.connections_per_second;
  return typeof value === "number" ? value : undefined;
}

function primaryThroughputComparison(comparison?: Schema<"PerformanceRunSummary">["throughput_comparison"]) {
  return comparison?.throughput_rps ?? comparison?.requests_per_second ?? comparison?.connections_per_second;
}

function metricProtocol(result: PerformanceResult) {
  const protocol = result.metrics.protocol;
  return typeof protocol === "string" && protocol ? protocol : "UNKNOWN";
}

function metricText(result: PerformanceResult, key: "response_code" | "failure_reason") {
  const value = result.metrics[key];
  return typeof value === "string" && value ? value : undefined;
}

function formatMs(value?: number) {
  return typeof value === "number" ? `${value.toFixed(1)} ms` : "-";
}

function formatPercent(value?: number) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "-";
}

function formatLatencyComparison(comparison?: { baseline_p95?: number; candidate_p95?: number }) {
  if (typeof comparison?.baseline_p95 !== "number" || typeof comparison.candidate_p95 !== "number") {
    return "-";
  }
  return `${comparison.baseline_p95.toFixed(1)} -> ${comparison.candidate_p95.toFixed(1)} ms`;
}

function formatThroughputComparison(comparison?: { baseline_value?: number; candidate_value?: number }) {
  if (typeof comparison?.baseline_value !== "number" || typeof comparison.candidate_value !== "number") {
    return "-";
  }
  return `${comparison.baseline_value.toFixed(1)} -> ${comparison.candidate_value.toFixed(1)} req/s`;
}

function formatRps(value?: number) {
  return typeof value === "number" ? `${value.toFixed(1)} req/s` : "-";
}

function shortAssetLabel(value: string) {
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-7)}`;
}

function averageNumber(values: Array<number | undefined>) {
  const numbers = values.filter((value): value is number => typeof value === "number");
  return numbers.length > 0 ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : undefined;
}

function formatSignedPercent(value?: number) {
  if (typeof value !== "number") {
    return "-";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}
