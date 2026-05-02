import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { JobStatus, Schema } from "../../api/types";
import { StatusBadge } from "../../components/common/Badges";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { Progress } from "../../components/ui/progress";
import { DataTable } from "../../components/ui/table";
import { statusLabel, yesNoLabel } from "../../domain/displayLabels";
import { canCancelJob, isActiveJobStatus, pageHasActiveJob } from "../../domain/jobStatus";
import { JobProgressModel } from "../../domain/models";
import { formatDateTime } from "../../lib/format";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import { buildDiscoveryCreatePayload } from "./discoveryCreatePayload";
import { DiscoveryPromotionModel } from "./discoveryPromotion";

export function DiscoveriesView() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<JobStatus | "">("");
  const [selectedDiscoveryIds, setSelectedDiscoveryIds] = useState<number[]>([]);
  const discoveries = useQuery({
    queryKey: queryKeys.discoveries.list(status || undefined),
    queryFn: () => services.discoveries.list(status || undefined),
    refetchInterval: (query) =>
      status === "RUNNING" || status === "PENDING" || (!status && pageHasActiveJob(query.state.data?.items)) ? 5_000 : false
  });
  const visibleDiscoveryIds = useMemo(() => discoveries.data?.items.map((item) => item.id) ?? [], [discoveries.data?.items]);
  const allVisibleSelected = visibleDiscoveryIds.length > 0 && visibleDiscoveryIds.every((id) => selectedDiscoveryIds.includes(id));

  useEffect(() => {
    const visibleIds = new Set(visibleDiscoveryIds);
    setSelectedDiscoveryIds((current) => {
      const next = current.filter((id) => visibleIds.has(id));
      return next.length === current.length ? current : next;
    });
  }, [visibleDiscoveryIds]);

  function toggleDiscovery(discoveryId: number, checked: boolean) {
    setSelectedDiscoveryIds((current) =>
      checked ? [...current.filter((id) => id !== discoveryId), discoveryId] : current.filter((id) => id !== discoveryId)
    );
  }

  return (
    <Section>
      <PageHeader
        title="CIDR 디스커버리"
        description="CIDR 기반으로 후보 엔드포인트를 찾고 스캔 대상으로 승인합니다."
        actions={
          <Button type="button" variant="primary" onClick={() => navigate("/discoveries/new")}>
            <Plus size={15} />CIDR 추가
          </Button>
        }
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Select aria-label="디스커버리 상태 필터" value={status} onChange={(event) => setStatus(event.target.value as JobStatus | "")}>
                <option value="">전체 상태</option>
                {["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"].map((item) => (
                  <option key={item} value={item}>
                    {statusLabel(item)}
                  </option>
                ))}
              </Select>
              <span className="muted">전체 {discoveries.data?.total ?? 0}</span>
            </div>
            <span className="inline-actions">
              <span className="muted">선택 {selectedDiscoveryIds.length}개</span>
              <Button type="button" size="sm" variant="ghost" disabled={selectedDiscoveryIds.length === 0} onClick={() => setSelectedDiscoveryIds([])}>
                선택 해제
              </Button>
            </span>
          </div>
        </CardContent>
      </Card>
      {discoveries.isLoading ? <LoadingState /> : null}
      {discoveries.isError ? <ErrorState error={discoveries.error} onRetry={() => void discoveries.refetch()} /> : null}
      {discoveries.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={discoveries.data.items}
              getRowKey={(item) => item.id}
              empty={<EmptyState title="디스커버리 작업이 없습니다" />}
              columns={[
                {
                  key: "select",
                  header: (
                    <Checkbox
                      aria-label="현재 표시된 디스커버리 전체 선택"
                      checked={allVisibleSelected}
                      disabled={visibleDiscoveryIds.length === 0}
                      onChange={(event) => setSelectedDiscoveryIds(event.target.checked ? visibleDiscoveryIds : [])}
                    />
                  ),
                  render: (item) => (
                    <Checkbox
                      aria-label={`디스커버리 #${item.id} 선택`}
                      checked={selectedDiscoveryIds.includes(item.id)}
                      onChange={(event) => toggleDiscovery(item.id, event.target.checked)}
                    />
                  )
                },
                { key: "id", header: "ID", render: (item) => <button className="link-button" onClick={() => navigate(`/discoveries/${item.id}`)}>#{item.id}</button> },
                { key: "cidr", header: "CIDR", render: (item) => item.cidr },
                { key: "ports", header: "포트", render: (item) => item.port_list.join(", ") || "기본값" },
                { key: "status", header: "상태", render: (item) => <StatusBadge status={item.status} /> },
                { key: "created", header: "생성", render: (item) => formatDateTime(item.created_at) }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}
    </Section>
  );
}

export function DiscoveryNewView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const trackJob = useJobWatchStore((state) => state.trackJob);
  const [cidr, setCidr] = useState("172.20.0.0/24");
  const [ports, setPorts] = useState("443,22,500");
  const [includeDefaultPorts, setIncludeDefaultPorts] = useState(true);
  const createPayload = useMemo(
    () => buildDiscoveryCreatePayload(cidr, ports, includeDefaultPorts),
    [cidr, includeDefaultPorts, ports]
  );
  const createDiscovery = useMutation({
    mutationFn: () => services.discoveries.create(createPayload.payload!),
    onSuccess: async (job) => {
      toast.success(`디스커버리 작업 #${job.id} 생성`);
      trackJob(job.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      navigate(`/discoveries/${job.resource.id}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "디스커버리 시작 실패")
  });

  return (
    <Section>
      <PageHeader title="CIDR 디스커버리 시작" description="CIDR 대역에서 스캔 후보 엔드포인트를 찾습니다." />
      <Card>
        <CardContent>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (!createPayload.payload) {
                return;
              }
              createDiscovery.mutate();
            }}
          >
            <fieldset className="form-fieldset" disabled={createDiscovery.isPending}>
              <div className="form-grid">
                <Field>
                  <FieldLabel>CIDR</FieldLabel>
                  <Input required value={cidr} onChange={(event) => setCidr(event.target.value)} />
                </Field>
                <Field>
                  <FieldLabel>포트</FieldLabel>
                  <Input value={ports} onChange={(event) => setPorts(event.target.value)} placeholder="443,22,500" />
                </Field>
                <Field className="is-wide">
                  <FieldLabel>기본 포트</FieldLabel>
                  <span className="inline-actions">
                    <Checkbox checked={includeDefaultPorts} onChange={(event) => setIncludeDefaultPorts(event.target.checked)} />
                    <span>프로토콜 기본 포트 포함</span>
                  </span>
                </Field>
              </div>
              {createPayload.errors.length > 0 ? <div className="callout state-view--error" role="alert">{createPayload.errors.join(" ")}</div> : null}
              <div className="form-actions">
                <Button type="button" variant="ghost" onClick={() => navigate("/discoveries")}>
                  취소
                </Button>
                <Button type="submit" variant="primary" disabled={!createPayload.payload || createDiscovery.isPending}>
                  <Play size={15} />{createDiscovery.isPending ? "시작 중" : "시작"}
                </Button>
              </div>
            </fieldset>
          </form>
        </CardContent>
      </Card>
    </Section>
  );
}

export function DiscoveryDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number[]>([]);
  const [confirmPromoteOpen, setConfirmPromoteOpen] = useState(false);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const discovery = useQuery({
    queryKey: queryKeys.discoveries.detail(id),
    queryFn: () => services.discoveries.get(id),
    refetchInterval: (query) => (query.state.data?.status === "RUNNING" || query.state.data?.status === "PENDING" ? 5_000 : false)
  });
  const endpoints = useQuery({
    queryKey: queryKeys.discoveries.endpoints(id),
    queryFn: () => services.discoveries.endpoints(id),
    refetchInterval: () => (isActiveJobStatus(discovery.data?.status) ? 5_000 : false)
  });
  const promotionModel = useMemo(() => new DiscoveryPromotionModel(endpoints.data?.items ?? []), [endpoints.data?.items]);
  const promotableIds = useMemo(() => promotionModel.promotableIds(), [promotionModel]);
  const promotionPayload = useMemo(() => promotionModel.payloadForSelected(selected), [promotionModel, selected]);
  const promote = useMutation({
    mutationFn: () => services.discoveries.promote(id, promotionPayload),
    onSuccess: async (result) => {
      toast.success(`${result.promoted.length}개 엔드포인트를 스캔 대상으로 승인했습니다.`);
      setSelected([]);
      await queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.endpoints(id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.all });
      navigate("/targets");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "스캔 대상 승인 실패")
  });
  const discoveryJobId = discovery.data?.job_id;
  const discoveryJob = useQuery({
    queryKey: discoveryJobId ? queryKeys.jobs.detail(discoveryJobId) : ["jobs", "detail", "discovery-none"],
    queryFn: () => services.jobs.get(discoveryJobId!),
    enabled: Boolean(discoveryJobId),
    refetchInterval: (query) => (isActiveJobStatus(query.state.data?.status) ? 3_000 : false)
  });
  const cancel = useMutation({
    mutationFn: () => services.jobs.cancel(discoveryJobId!),
    onSuccess: async (job) => {
      toast.success("디스커버리 취소 요청을 보냈습니다.");
      setCancelRequested(true);
      queryClient.setQueryData(queryKeys.jobs.detail(job.id), job);
      queryClient.setQueryData(queryKeys.discoveries.detail(id), (current: Schema<"Discovery"> | undefined) =>
        current
          ? {
              ...current,
              status: job.status,
              progress: job.progress ?? current.progress,
              finished_at: job.finished_at ?? current.finished_at,
              error: job.status === "CANCELLED" ? (current.error ?? "cancel_requested") : current.error
            }
          : current
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.detail(id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.endpoints(id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "취소 실패")
  });

  useEffect(() => {
    setSelected((current) => current.filter((endpointId) => promotableIds.includes(endpointId)));
  }, [promotableIds]);

  useEffect(() => {
    if (discovery.data && !isActiveJobStatus(discovery.data.status)) {
      setCancelRequested(false);
      void queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.endpoints(id) });
    }
  }, [discovery.data?.status, id, queryClient]);

  if (discovery.isLoading) {
    return <LoadingState />;
  }
  if (discovery.isError || !discovery.data) {
    return <ErrorState error={discovery.error} onRetry={() => void discovery.refetch()} />;
  }

  const progress = new JobProgressModel(discovery.data.progress);
  const canCancel = Boolean(discoveryJobId) && (discoveryJob.data ? canCancelJob(discoveryJob.data) : isActiveJobStatus(discovery.data.status) && !cancelRequested);

  return (
    <Section>
      <PageHeader
        title={`디스커버리 #${discovery.data.id}`}
        description={discovery.data.cidr}
        actions={
          <>
            <Button type="button" variant="danger" disabled={!canCancel || cancel.isPending} onClick={() => setConfirmCancelOpen(true)}>
              <XCircle size={15} />취소
            </Button>
            <Button type="button" variant="primary" disabled={selected.length === 0 || promote.isPending} onClick={() => setConfirmPromoteOpen(true)}>
              스캔 대상으로 승인
            </Button>
          </>
        }
      />
      <ConfirmDialog
        open={confirmCancelOpen}
        title="디스커버리 취소"
        description={`디스커버리 #${discovery.data.id} 취소를 요청합니다. 이미 발견된 엔드포인트는 부분 결과로 남습니다.`}
        confirmLabel="취소 요청"
        pending={cancel.isPending}
        onCancel={() => setConfirmCancelOpen(false)}
        onConfirm={() => cancel.mutate(undefined, { onSettled: () => setConfirmCancelOpen(false) })}
      />
      <ConfirmDialog
        open={confirmPromoteOpen}
        title="스캔 대상 승인"
        description={`선택한 엔드포인트 ${selected.length}개를 스캔 대상으로 추가합니다.`}
        confirmLabel="승인"
        confirmVariant="primary"
        pending={promote.isPending}
        onCancel={() => setConfirmPromoteOpen(false)}
        onConfirm={() => promote.mutate(undefined, { onSettled: () => setConfirmPromoteOpen(false) })}
      />
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>상태</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>상태</dt><dd><StatusBadge status={discovery.data.status} /></dd></div>
              <div><dt>생성</dt><dd>{formatDateTime(discovery.data.created_at)}</dd></div>
              <div><dt>시작</dt><dd>{formatDateTime(discovery.data.started_at)}</dd></div>
              <div><dt>종료</dt><dd>{formatDateTime(discovery.data.finished_at)}</dd></div>
            </dl>
            <div className="callout">
              <Progress value={progress.percent()} />
              <p className="muted">{progress.label()}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>스캔 대상 승인</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="muted">승인할 엔드포인트를 명시적으로 선택하세요. 선택하지 않은 엔드포인트는 스캔 대상으로 추가하지 않습니다.</p>
            <div className="inline-actions">
              <Button type="button" onClick={() => setSelected(promotableIds)} disabled={promotableIds.length === 0}>
                전체 선택
              </Button>
              <Button type="button" variant="ghost" onClick={() => setSelected([])} disabled={selected.length === 0}>
                선택 해제
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>엔드포인트</CardTitle>
        </CardHeader>
        <CardContent>
          {endpoints.isLoading ? <LoadingState /> : null}
          {endpoints.isError ? <ErrorState error={endpoints.error} onRetry={() => void endpoints.refetch()} /> : null}
          {endpoints.data ? (
            <DataTable
              items={endpoints.data.items}
              getRowKey={(endpoint) => endpoint.id}
              columns={[
                {
                  key: "select",
                  header: "",
                  render: (endpoint) => (
                    <Checkbox
                      aria-label={`${endpoint.suggested_host ?? endpoint.ip}:${endpoint.port} 스캔 대상 승인 선택`}
                      checked={selected.includes(endpoint.id)}
                      disabled={endpoint.promoted}
                      onChange={(event) =>
                        setSelected((current) =>
                          event.target.checked ? [...current, endpoint.id] : current.filter((item) => item !== endpoint.id)
                        )
                      }
                    />
                  )
                },
                { key: "host", header: "호스트/IP", render: (endpoint) => endpoint.suggested_host ?? endpoint.ip },
                { key: "port", header: "포트", render: (endpoint) => endpoint.port },
                { key: "protocol", header: "프로토콜", render: (endpoint) => endpoint.suggested_protocol_hint ?? endpoint.detected_protocol ?? "-" },
                { key: "promoted", header: "승인 여부", render: (endpoint) => yesNoLabel(endpoint.promoted) },
                { key: "target", header: "스캔 대상", render: (endpoint) => endpoint.target_id ? `#${endpoint.target_id}` : "-" }
              ]}
            />
          ) : null}
        </CardContent>
      </Card>
    </Section>
  );
}
