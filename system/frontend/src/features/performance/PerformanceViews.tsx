import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { MetricCard } from "../../components/charts/MetricCard";
import { Badge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Field, FieldLabel, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { performanceStatusLabel, profileLabel } from "../../domain/displayLabels";
import { formatDateTime, formatNumber } from "../../lib/format";

type PerformanceRun = Schema<"PerformanceEvaluationRun">;
type PerformanceResult = Schema<"AssetPerformanceResult">;
type PerformanceProfile = Schema<"PerformanceRunProfile">;

const profiles: PerformanceProfile[] = ["smoke", "baseline", "canary", "stress"];

export function PerformanceEvaluationView({ snapshotId }: { snapshotId: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const profileParam = searchParams.get("profile") ?? "";
  const selectedRunId = searchParams.get("run") ? Number(searchParams.get("run")) : undefined;
  const profile = profiles.includes(profileParam as PerformanceProfile) ? (profileParam as PerformanceProfile) : "";
  const filters = useMemo(() => ({ profile: profile || undefined }), [profile]);
  const runs = useQuery({
    queryKey: queryKeys.performance.runs(snapshotId, filters),
    queryFn: () => services.performance.listRuns(snapshotId, filters)
  });
  const runItems = runs.data?.items ?? [];
  const activeRunId = selectedRunId && runItems.some((run) => run.id === selectedRunId) ? selectedRunId : runItems[0]?.id;
  const detail = useQuery({
    queryKey: queryKeys.performance.detail(snapshotId, activeRunId ?? 0),
    queryFn: () => services.performance.getRun(snapshotId, activeRunId!),
    enabled: Boolean(activeRunId)
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
        title={`스냅샷 #${snapshotId} 성능평가`}
        description="PQC 전환 전후 성능평가 실행과 자산별 측정 결과를 조회합니다."
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Field className="field-inline">
                <FieldLabel>프로파일</FieldLabel>
                <Select aria-label="성능평가 프로파일 필터" value={profile} onChange={(event) => setFilter("profile", event.target.value)}>
                  <option value="">전체 프로파일</option>
                  {profiles.map((item) => (
                    <option key={item} value={item}>{profileLabel(item)}</option>
                  ))}
                </Select>
              </Field>
              <Field className="field-inline">
                <FieldLabel>실행</FieldLabel>
                <Select
                  aria-label="성능평가 실행 선택"
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
        <EmptyState title="성능평가 실행이 없습니다" description="마이그레이션 후 에이전트가 성능 측정 결과를 업로드하면 이곳에 표시됩니다." />
      ) : null}
      {detail.isLoading && activeRunId ? <LoadingState /> : null}
      {detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : null}
      {detail.data ? <PerformanceRunDetail run={detail.data} /> : null}
    </Section>
  );
}

function PerformanceRunDetail({ run }: { run: Schema<"PerformanceEvaluationRunDetail"> }) {
  const summary = run.summary;
  const warnFailCount = (summary.by_status.WARN ?? 0) + (summary.by_status.FAIL ?? 0) + (summary.by_status.ERROR ?? 0);
  return (
    <div className="section-stack">
      <div className="content-grid content-grid--4">
        <MetricCard label="전체 상태" value={performanceStatusLabel(summary.overall_status)} />
        <MetricCard label="결과 수" value={formatNumber(summary.total_results)} />
        <MetricCard label="경고/실패" value={formatNumber(warnFailCount)} />
        <MetricCard label="기준 스냅샷" value={run.baseline_snapshot_id ? `#${run.baseline_snapshot_id}` : "-"} />
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
      <Card>
        <CardHeader>
          <CardTitle>자산별 결과</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            items={run.results}
            getRowKey={(item) => item.id}
            empty={<EmptyState title="자산별 성능 결과가 없습니다" />}
            columns={[
              { key: "asset", header: "자산", render: (item) => <span className="mono">{item.bom_ref}</span> },
              { key: "target", header: "스캔 대상", render: (item) => item.target_label ?? "-" },
              { key: "status", header: "상태", render: (item) => <PerformanceStatusBadge status={item.status} /> },
              { key: "compatibility", header: "호환성", render: (item) => <PerformanceStatusBadge status={item.compatibility_status} /> },
              { key: "algorithm", header: "협상 알고리즘", render: (item) => item.negotiated_algorithm || "-" },
              { key: "handshake", header: "핸드셰이크 p95", align: "right", render: (item) => formatMs(metricP95(item, "handshake_ms")) },
              { key: "ttfb", header: "TTFB p95", align: "right", render: (item) => formatMs(metricP95(item, "ttfb_ms")) },
              { key: "failure", header: "실패율", align: "right", render: (item) => formatPercent(numberMetric(item, "failure_rate")) },
              { key: "delta", header: "핸드셰이크 변화율", align: "right", render: (item) => formatSignedPercent(item.deltas.handshake_p95_percent) },
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

function numberMetric(result: PerformanceResult, key: "failure_rate" | "timeout_rate" | "session_resumption_rate") {
  const value = result.metrics[key];
  return typeof value === "number" ? value : undefined;
}

function formatMs(value?: number) {
  return typeof value === "number" ? `${value.toFixed(1)} ms` : "-";
}

function formatPercent(value?: number) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "-";
}

function formatSignedPercent(value?: number) {
  if (typeof value !== "number") {
    return "-";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}
