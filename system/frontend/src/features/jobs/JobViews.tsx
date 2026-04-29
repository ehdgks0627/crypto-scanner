import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { JobStatus, ScannerId } from "../../api/types";
import { StatusBadge } from "../../components/common/Badges";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Select } from "../../components/ui/form";
import { Progress } from "../../components/ui/progress";
import { DataTable } from "../../components/ui/table";
import { canCancelJob, pageHasActiveJob } from "../../domain/jobStatus";
import { JobProgressModel } from "../../domain/models";
import { formatDateTime } from "../../lib/format";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import { ScanSelectionModel } from "./scanSelection";

function formatJobError(value: unknown): string | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  if (value instanceof Error) {
    return value.message;
  }
  if (typeof value === "object") {
    const message = "message" in value ? value.message : undefined;
    const code = "code" in value ? value.code : undefined;
    if (typeof message === "string" && message.trim()) {
      return typeof code === "string" && code.trim() ? `${code}: ${message}` : message;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return "알 수 없는 오류";
    }
  }
  return String(value);
}

export function JobsView() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const status = (searchParams.get("status") ?? "") as JobStatus | "";
  const jobs = useQuery({
    queryKey: queryKeys.jobs.list(status || undefined),
    queryFn: () => services.jobs.list(status || undefined),
    refetchInterval: (query) =>
      status === "RUNNING" || status === "PENDING" || (!status && pageHasActiveJob(query.state.data?.items)) ? 5_000 : false
  });

  return (
    <Section>
      <PageHeader
        title="Scan Jobs"
        description="스캔 작업 생성, 진행 상태, 로그를 관리합니다."
        actions={
          <Button type="button" variant="primary" onClick={() => navigate("/scans/new")}>
            <Play size={15} />새 스캔
          </Button>
        }
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <Select aria-label="Job status filter" value={status} onChange={(event) => setSearchParams(event.target.value ? { status: event.target.value } : {})}>
              <option value="">All statuses</option>
              {["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
            <span className="muted">Total {jobs.data?.total ?? 0}</span>
          </div>
        </CardContent>
      </Card>
      {jobs.isLoading ? <LoadingState /> : null}
      {jobs.isError ? <ErrorState error={jobs.error} onRetry={() => void jobs.refetch()} /> : null}
      {jobs.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={jobs.data.items}
              getRowKey={(job) => job.id}
              empty={<EmptyState title="스캔 작업이 없습니다" />}
              columns={[
                { key: "id", header: "Job", render: (job) => <button className="link-button" onClick={() => navigate(`/scans/${job.id}`)}>#{job.id}</button> },
                { key: "kind", header: "Kind", render: (job) => job.kind },
                { key: "status", header: "Status", render: (job) => <StatusBadge status={job.status} /> },
                { key: "resource", header: "Resource", render: (job) => `${job.resource.kind} #${job.resource.id}` },
                { key: "started", header: "Started", render: (job) => formatDateTime(job.started_at) },
                { key: "finished", header: "Finished", render: (job) => formatDateTime(job.finished_at) }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}
    </Section>
  );
}

export function ScanNewView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const trackJob = useJobWatchStore((state) => state.trackJob);
  const [searchParams] = useSearchParams();
  const preselectedTargetIds = useMemo(() => ScanSelectionModel.targetIdsFromSearch(searchParams), [searchParams]);
  const [targetIds, setTargetIds] = useState<number[]>(preselectedTargetIds);
  const [scanners, setScanners] = useState<ScannerId[]>([]);
  const targets = useQuery({
    queryKey: queryKeys.targets.list({ limit: 100 }),
    queryFn: () => services.targets.list({ limit: 100 })
  });
  const scannerMeta = useQuery({
    queryKey: queryKeys.meta.scanners,
    queryFn: () => services.meta.scanners()
  });
  const createJob = useMutation({
    mutationFn: () => services.jobs.create({ target_ids: targetIds, scanners }),
    onSuccess: async (job) => {
      toast.success(`Scan job #${job.id} 생성`);
      trackJob(job.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      navigate(`/scans/${job.id}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "스캔 시작 실패")
  });
  const validTargetIds = useMemo(() => new Set((targets.data?.items ?? []).map((target) => target.id)), [targets.data?.items]);
  const missingPreselectedIds = targets.data ? preselectedTargetIds.filter((id) => !validTargetIds.has(id)) : [];
  const estimatedRuns = targetIds.length * scanners.length;

  useEffect(() => {
    setTargetIds(preselectedTargetIds);
  }, [preselectedTargetIds]);

  useEffect(() => {
    if (targets.data) {
      setTargetIds((current) => current.filter((id) => validTargetIds.has(id)));
    }
  }, [targets.data, validTargetIds]);

  return (
    <Section>
      <PageHeader title="Scan Job 시작" description="타겟과 스캐너를 선택해 새 스캔을 실행합니다." />
      <div className="split-pane">
        <Card>
          <CardHeader>
            <CardTitle>Targets</CardTitle>
          </CardHeader>
          <CardContent>
            {targets.isLoading ? <LoadingState /> : null}
            {targets.isError ? <ErrorState error={targets.error} onRetry={() => void targets.refetch()} /> : null}
            {missingPreselectedIds.length > 0 ? (
              <div className="callout state-view--error">선택한 target #{missingPreselectedIds.join(", #")}를 찾을 수 없습니다.</div>
            ) : null}
            {targets.data ? (
              <DataTable
                items={targets.data.items}
                getRowKey={(target) => target.id}
                columns={[
                  {
                    key: "select",
                    header: "",
                    render: (target) => (
                      <Checkbox
                        aria-label={`${target.host} 스캔 대상 선택`}
                        checked={targetIds.includes(target.id)}
                        onChange={(event) =>
                          setTargetIds((current) => (event.target.checked ? [...current, target.id] : current.filter((id) => id !== target.id)))
                        }
                      />
                    )
                  },
                  { key: "host", header: "Host", render: (target) => target.host },
                  { key: "endpoint", header: "Endpoint", render: (target) => `${target.transport}/${target.port}` },
                  { key: "agent", header: "Agent", render: (target) => (target.agent_enabled ? "yes" : "no") }
                ]}
              />
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Scanners</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="section-stack">
              {scannerMeta.isError ? <ErrorState error={scannerMeta.error} onRetry={() => void scannerMeta.refetch()} /> : null}
              {scannerMeta.isLoading ? <LoadingState /> : null}
              {scannerMeta.data && scannerMeta.data.scanners.length === 0 ? <EmptyState title="사용 가능한 스캐너가 없습니다" /> : null}
              {(scannerMeta.data?.scanners ?? []).map((scanner) => (
                <label key={scanner.id} className="callout inline-actions">
                  <Checkbox
                    checked={scanners.includes(scanner.id)}
                    onChange={(event) =>
                      setScanners((current) => (event.target.checked ? [...current, scanner.id] : current.filter((id) => id !== scanner.id)))
                    }
                  />
                  <span>{scanner.label}</span>
                  {scanner.requires_agent ? <span className="muted">agent</span> : null}
                </label>
              ))}
              <div className="callout">
                <strong>{estimatedRuns}</strong>
                <p className="muted">예상 실행 수</p>
              </div>
              <Button
                type="button"
                variant="primary"
                disabled={targetIds.length === 0 || scanners.length === 0 || createJob.isPending || targets.isError || scannerMeta.isError}
                onClick={() => createJob.mutate()}
              >
                <Play size={15} />스캔 시작
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}

export function JobDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [handledTerminalStatus, setHandledTerminalStatus] = useState<string | null>(null);
  const job = useQuery({
    queryKey: queryKeys.jobs.detail(id),
    queryFn: () => services.jobs.get(id),
    refetchInterval: (query) => (query.state.data?.status === "RUNNING" || query.state.data?.status === "PENDING" ? 5_000 : false)
  });
  const logs = useQuery({
    queryKey: queryKeys.jobs.logs(id),
    queryFn: () => services.jobs.logs(id),
    refetchInterval: job.data?.status === "RUNNING" ? 5_000 : false
  });
  const cancel = useMutation({
    mutationFn: () => services.jobs.cancel(id),
    onSuccess: async () => {
      toast.success("취소 요청을 보냈습니다.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs.detail(id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "취소 실패")
  });

  useEffect(() => {
    const status = job.data?.status;
    if (!status || status === "PENDING" || status === "RUNNING" || handledTerminalStatus === status) {
      return;
    }
    setHandledTerminalStatus(status);
    void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.logs(id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
    if (job.data?.result?.snapshot_id) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.detail(job.data.result.snapshot_id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(job.data.result.snapshot_id) });
    }
  }, [handledTerminalStatus, id, job.data, queryClient]);

  if (job.isLoading) {
    return <LoadingState />;
  }
  if (job.isError || !job.data) {
    return <ErrorState error={job.error} onRetry={() => void job.refetch()} />;
  }

  const progress = new JobProgressModel(job.data.progress);
  const canCancel = canCancelJob(job.data);
  const jobError = formatJobError(job.data.error);

  return (
    <Section>
      <PageHeader
        title={`Job #${job.data.id}`}
        description={`${job.data.kind} · resource #${job.data.resource.id}`}
        actions={
          <Button type="button" variant="danger" disabled={!canCancel || cancel.isPending} onClick={() => setConfirmCancelOpen(true)}>
            <XCircle size={15} />취소
          </Button>
        }
      />
      <ConfirmDialog
        open={confirmCancelOpen}
        title="Job 취소"
        description={`Job #${job.data.id} 취소를 요청합니다. 이미 실행된 작업 결과는 되돌리지 않습니다.`}
        confirmLabel="취소 요청"
        pending={cancel.isPending}
        onCancel={() => setConfirmCancelOpen(false)}
        onConfirm={() => cancel.mutate(undefined, { onSettled: () => setConfirmCancelOpen(false) })}
      />
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>진행 상태</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>Status</dt><dd><StatusBadge status={job.data.status} /></dd></div>
              <div><dt>Started</dt><dd>{formatDateTime(job.data.started_at)}</dd></div>
              <div><dt>Cancel Requested</dt><dd>{formatDateTime(job.data.cancel_requested_at)}</dd></div>
              <div><dt>Finished</dt><dd>{formatDateTime(job.data.finished_at)}</dd></div>
            </dl>
            <div className="callout" role="status" aria-live="polite">
              <Progress value={progress.percent()} />
              <p className="muted">{progress.label()}</p>
            </div>
            {jobError ? <p className="state-view--error" role="alert">{jobError}</p> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div>
                <dt>Snapshot</dt>
                <dd>
                  {job.data.result?.snapshot_id ? (
                    <button className="link-button" type="button" onClick={() => navigate(`/snapshots/${job.data.result?.snapshot_id}`)}>
                      #{job.data.result.snapshot_id}
                    </button>
                  ) : (
                    "-"
                  )}
                </dd>
              </div>
              <div>
                <dt>Discovery</dt>
                <dd>
                  {job.data.result?.discovery_id ? (
                    <button className="link-button" type="button" onClick={() => navigate(`/discoveries/${job.data.result?.discovery_id}`)}>
                      #{job.data.result.discovery_id}
                    </button>
                  ) : (
                    "-"
                  )}
                </dd>
              </div>
              <div><dt>Updated Scores</dt><dd>{job.data.result?.updated_scores_count ?? "-"}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Run Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {logs.isLoading ? <LoadingState /> : null}
          {logs.isError ? <ErrorState error={logs.error} onRetry={() => void logs.refetch()} /> : null}
          {logs.data ? (
            <DataTable
              items={logs.data.items}
              getRowKey={(log) => log.id}
              empty={<EmptyState title="로그가 없습니다" />}
              columns={[
                { key: "target", header: "Target", render: (log) => log.target_label },
                { key: "scanner", header: "Scanner", render: (log) => log.scanner_kind },
                { key: "status", header: "Status", render: (log) => <StatusBadge status={log.status} /> },
                { key: "findings", header: "Findings", render: (log) => log.findings_count },
                { key: "started", header: "Started", render: (log) => formatDateTime(log.started_at) },
                { key: "error", header: "Error", render: (log) => formatJobError(log.error) ?? "-" }
              ]}
            />
          ) : null}
        </CardContent>
      </Card>
    </Section>
  );
}
