import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Download, Save, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { DhsPriorityBadge, RiskTierBadge } from "../../components/common/Badges";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { MetricCard } from "../../components/charts/MetricCard";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Field, FieldHint, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import {
  assetClassLabel,
  assetTypeLabel,
  contextFieldLabel,
  contextValueLabel,
  exposureLabel,
  levelLabel,
  performanceStatusLabel,
  riskTierLabel,
  statusLabel
} from "../../domain/displayLabels";
import { parseRiskTierParam, riskTierOptions } from "../../domain/filterOptions";
import { isTerminalJobStatus } from "../../domain/jobStatus";
import { formatDateTime, formatOptionalScore, formatScore } from "../../lib/format";
import { downloadJson } from "../../lib/download";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import {
  assetContextToFormValues,
  buildAssetContextPatch,
  validateAssetContextPatchValues
} from "./assetContextPatch";
import { useSelectedSnapshot } from "./useSelectedSnapshot";

export function SnapshotsView() {
  const { snapshots, selectedSnapshot, selectedSnapshotId } = useSelectedSnapshot();

  if (snapshots.isLoading) {
    return <LoadingState />;
  }
  if (snapshots.isError) {
    return <ErrorState error={snapshots.error} onRetry={() => void snapshots.refetch()} />;
  }
  if (!selectedSnapshotId) {
    return (
      <Section>
        <PageHeader title="식별 자산" description="헤더에서 선택한 스냅샷 기준으로 식별 자산을 조회합니다." />
        <EmptyState title="식별 자산이 없습니다" description="스캔이 완료되면 최신 스냅샷의 자산 목록이 이곳에 표시됩니다." />
      </Section>
    );
  }

  return <SnapshotAssetsView id={selectedSnapshotId} snapshotHint={selectedSnapshot ?? undefined} />;
}

export function SnapshotDetailView({ id }: { id: number }) {
  return <SnapshotAssetsView id={id} />;
}

function SnapshotAssetsView({ id, snapshotHint }: { id: number; snapshotHint?: Schema<"CbomSnapshot"> }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [exportingCbom, setExportingCbom] = useState(false);
  const tier = parseRiskTierParam(searchParams.get("tier"));
  const q = searchParams.get("q") ?? "";
  const snapshot = useQuery({
    queryKey: queryKeys.snapshots.detail(id),
    queryFn: () => services.snapshots.get(id),
    initialData: snapshotHint
  });
  const filters = useMemo(() => ({ tier: tier ? [tier] : undefined, q: q || undefined, sort: "-risk_score" }), [tier, q]);
  const assets = useQuery({
    queryKey: queryKeys.snapshots.assets(id, filters),
    queryFn: () => services.snapshots.assets(id, filters)
  });

  async function exportCbom() {
    setExportingCbom(true);
    try {
      const document = await services.snapshots.export(id);
      downloadJson(`cbom-${id}.json`, document);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "CBOM JSON 다운로드 실패");
    } finally {
      setExportingCbom(false);
    }
  }

  if (snapshot.isLoading) {
    return <LoadingState />;
  }
  if (snapshot.isError || !snapshot.data) {
    return <ErrorState error={snapshot.error} onRetry={() => void snapshot.refetch()} />;
  }

  return (
    <Section>
      <PageHeader
        title="식별 자산"
        description={`스냅샷 #${snapshot.data.id} · ${formatDateTime(snapshot.data.created_at)}`}
        actions={
          <>
            <Button type="button" disabled={exportingCbom} onClick={() => void exportCbom()}>
              <Download size={15} />CBOM JSON
            </Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/diff`)}>비교</Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/risk`)}>위험평가</Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/migration`)}>Review Targets</Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/performance`)}>가용성 검사</Button>
          </>
        }
      />
      <div className="content-grid content-grid--4">
        <MetricCard label="식별 자산" value={snapshot.data.asset_count} />
        <MetricCard label="치명 위험" value={snapshot.data.summary.by_tier?.CRITICAL ?? 0} />
        <MetricCard label="높은 위험" value={snapshot.data.summary.by_tier?.HIGH ?? 0} />
        <MetricCard label="검증 오류" value={snapshot.data.validation_errors.length} />
      </div>
      <Card>
        <CardContent>
          <div className="toolbar toolbar--asset-filters">
            <div className="toolbar__filters">
              <Input className="asset-filter-search" aria-label="자산 검색" value={q} onChange={(event) => setSearchParams({ ...(tier ? { tier } : {}), ...(event.target.value ? { q: event.target.value } : {}) })} placeholder="자산 검색" />
              <Select className="asset-filter-tier" aria-label="자산 위험도 필터" value={tier ?? ""} onChange={(event) => setSearchParams({ ...(event.target.value ? { tier: event.target.value } : {}), ...(q ? { q } : {}) })}>
                <option value="">전체 등급</option>
                {riskTierOptions.map((item) => (
                  <option key={item} value={item}>
                    {riskTierLabel(item)}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="button" variant="ghost" onClick={() => setSearchParams({})}>필터 초기화</Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>식별 자산 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {assets.isLoading ? <LoadingState /> : null}
          {assets.isError ? <ErrorState error={assets.error} onRetry={() => void assets.refetch()} /> : null}
          {assets.data ? (
            <DataTable
              items={assets.data.items}
              getRowKey={(asset) => asset.id}
              empty={<EmptyState title="식별 자산이 없습니다" />}
              columns={[
                { key: "name", header: "이름", render: (asset) => <button className="link-button" onClick={() => navigate(`/snapshots/${id}/assets/${asset.id}`)}>{asset.name}</button> },
                { key: "class", header: "분류", render: (asset) => assetClassLabel(asset.asset_class) },
                { key: "type", header: "타입", render: (asset) => assetTypeLabel(asset.asset_type) },
                { key: "target", header: "스캔 대상", render: (asset) => asset.target_label ?? (asset.target_id ? `#${asset.target_id}` : "-") },
                { key: "score", header: "점수", render: (asset) => formatScore(asset.risk?.score) },
                { key: "tier", header: "등급", render: (asset) => <RiskTierBadge tier={asset.risk?.tier} /> },
                { key: "dhs-score", header: "DHS 점수", render: (asset) => formatOptionalScore(asset.risk?.dhs_risk?.score_10), align: "right" },
                { key: "dhs-priority", header: "우선순위", render: (asset) => <DhsPriorityBadge priority={asset.risk?.dhs_risk?.priority} /> }
              ]}
            />
          ) : null}
        </CardContent>
      </Card>
    </Section>
  );
}

export function AssetDetailView({ snapshotId, assetId }: { snapshotId: number; assetId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const trackJob = useJobWatchStore((state) => state.trackJob);
  const [editing, setEditing] = useState(false);
  const [recomputeJobId, setRecomputeJobId] = useState<number | null>(null);
  const asset = useQuery({
    queryKey: queryKeys.assets.detail(assetId),
    queryFn: () => services.assets.get(assetId)
  });
  const performanceHistory = useQuery({
    queryKey: queryKeys.performance.history(assetId),
    queryFn: () => services.performance.history(assetId)
  });
  const patchContext = useMutation({
    mutationFn: (payload: Schema<"AssetContextPatch">) => services.assets.patchContext(assetId, payload),
    onSuccess: async (result) => {
      toast.success(`저장했습니다. 재계산 작업 #${result.recompute_job_id}`);
      setEditing(false);
      setRecomputeJobId(result.recompute_job_id);
      trackJob(result.recompute_job_id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(snapshotId) });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "저장 실패")
  });
  const suggestContext = useMutation({
    mutationFn: () => services.assets.contextSuggestion(assetId)
  });
  const recomputeJob = useQuery({
    queryKey: recomputeJobId ? queryKeys.jobs.detail(recomputeJobId) : ["jobs", "detail", "asset-context-none"],
    queryFn: () => services.jobs.get(recomputeJobId!),
    enabled: Boolean(recomputeJobId),
    refetchInterval: (query) => (query.state.data?.status === "PENDING" || query.state.data?.status === "RUNNING" ? 3_000 : false)
  });

  useEffect(() => {
    if (recomputeJob.data?.status === "COMPLETED") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.listPrefix(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.top(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.migration.planPrefix(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      toast.success("자산 컨텍스트 재계산 완료");
      setRecomputeJobId(null);
    }
    if (recomputeJob.data?.status && isTerminalJobStatus(recomputeJob.data.status) && recomputeJob.data.status !== "COMPLETED") {
      toast.error(recomputeJob.data.status === "CANCELLED" ? "자산 컨텍스트 재계산 취소됨" : "자산 컨텍스트 재계산 실패");
      setRecomputeJobId(null);
    }
  }, [assetId, queryClient, recomputeJob.data?.status, snapshotId]);

  if (asset.isLoading) {
    return <LoadingState />;
  }
  if (asset.isError || !asset.data) {
    return <ErrorState error={asset.error} onRetry={() => void asset.refetch()} />;
  }

  return (
    <Section>
      <PageHeader
        title={asset.data.name}
        description={`${assetClassLabel(asset.data.asset_class)} · ${assetTypeLabel(asset.data.asset_type)}`}
      />
      {recomputeJob.data ? <div className="callout" role="status" aria-live="polite">재계산 #{recomputeJob.data.id}: {statusLabel(recomputeJob.data.status)}</div> : null}
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>자산 정보</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>ID</dt><dd>#{asset.data.id}</dd></div>
              <div><dt>BOM 참조</dt><dd className="mono">{asset.data.bom_ref ?? "-"}</dd></div>
              <div><dt>스캔 대상</dt><dd>{asset.data.target?.host ?? "-"}</dd></div>
              <div><dt>위험도</dt><dd>{asset.data.risk ? <RiskTierBadge tier={asset.data.risk.tier} /> : "-"}</dd></div>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>평가 기준 컨텍스트</CardTitle>
            <Button type="button" variant={editing ? "ghost" : "primary"} onClick={() => setEditing((value) => !value)}>
              <Save size={15} />{editing ? "보기" : "컨텍스트 수정"}
            </Button>
          </CardHeader>
          <CardContent>
            {editing ? (
              <AssetContextForm
                initialValue={asset.data.effective_context}
                contextSources={asset.data.context_sources}
                isSubmitting={patchContext.isPending}
                isSuggesting={suggestContext.isPending}
                onCancel={() => setEditing(false)}
                onSuggest={() => suggestContext.mutateAsync()}
                onSubmit={(payload) => patchContext.mutate(payload)}
              />
            ) : (
              <dl className="detail-list">
                {Object.entries(asset.data.effective_context).map(([key, value]) => (
                  <div key={key}>
                    <dt>{contextFieldLabel(key)}</dt>
                    <dd>{contextValueLabel(key, value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>가용성 검사 이력</CardTitle>
        </CardHeader>
        <CardContent>
          {performanceHistory.isLoading ? <LoadingState /> : null}
          {performanceHistory.isError ? <ErrorState error={performanceHistory.error} onRetry={() => void performanceHistory.refetch()} /> : null}
          {performanceHistory.data ? (
            <DataTable
              items={performanceHistory.data.items}
              getRowKey={(item) => item.id}
              empty={<EmptyState title="가용성 검사 이력이 없습니다" />}
              columns={[
                { key: "run", header: "실행", render: (item) => `#${item.run_id}` },
                { key: "status", header: "상태", render: (item) => performanceStatusLabel(item.status) },
                { key: "algorithm", header: "협상 알고리즘", render: (item) => item.negotiated_algorithm || "-" },
                { key: "handshake", header: "핸드셰이크 p95", align: "right", render: (item) => formatAssetPerfMs(item.metrics.handshake_ms?.p95) },
                { key: "delta", header: "핸드셰이크 변화율", align: "right", render: (item) => formatAssetPerfDelta(item.deltas.handshake_p95_percent) },
                { key: "measured", header: "측정 시각", render: (item) => formatDateTime(item.measured_at) }
              ]}
            />
          ) : null}
        </CardContent>
      </Card>
      <EnrichedCbomCard component={asset.data.enriched_cbom_component} />
    </Section>
  );
}

function EnrichedCbomCard({ component }: { component: unknown }) {
  const [open, setOpen] = useState(false);
  const cbom = asRecord(component);
  const rows = cbomComponentRows(cbom);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Enriched CBOM</CardTitle>
        <Button type="button" variant="ghost" onClick={() => setOpen((value) => !value)}>
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}{open ? "접기" : "펼치기"}
        </Button>
      </CardHeader>
      {open ? (
        <CardContent>
          <DataTable
            items={rows}
            getRowKey={(item) => item.name}
            empty={<EmptyState title="CBOM 속성이 없습니다" />}
            columns={[
              { key: "name", header: "속성", render: (item) => <span className="mono">{item.name}</span> },
              { key: "value", header: "값", render: (item) => <span className="mono">{item.value}</span> }
            ]}
          />
        </CardContent>
      ) : null}
    </Card>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function cbomComponentRows(component: Record<string, unknown>) {
  const cryptoProperties = asRecord(component.cryptoProperties);
  const rows = [
    { name: "bom-ref", value: stringValue(component["bom-ref"]) },
    { name: "type", value: stringValue(component.type) },
    { name: "name", value: stringValue(component.name) },
    { name: "crypto.assetType", value: stringValue(cryptoProperties.assetType) },
    { name: "crypto.algorithm", value: stringValue(cryptoProperties.algorithm) },
    { name: "crypto.algorithmFamily", value: stringValue(cryptoProperties.algorithmFamily) }
  ];
  const properties = component.properties;
  if (!Array.isArray(properties)) {
    return rows;
  }
  return rows.concat(
    properties
    .map((item) => asRecord(item))
    .filter((item) => typeof item.name === "string")
    .map((item) => ({ name: String(item.name), value: stringValue(item.value) }))
  );
}

function stringValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function formatJsonPreview(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function formatAiResponsePreview(response: Schema<"AssetContextSuggestion">["llm_trace"]["response"]) {
  return formatJsonPreview({
    raw: prettyJsonString(response.raw),
    parsed: response.parsed
  });
}

function prettyJsonString(value: string) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function formatAssetPerfMs(value?: number) {
  return typeof value === "number" ? `${value.toFixed(1)} ms` : "-";
}

function formatAssetPerfDelta(value?: number) {
  if (typeof value !== "number") {
    return "-";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function AssetContextForm({
  initialValue,
  contextSources,
  isSubmitting = false,
  isSuggesting = false,
  onSubmit,
  onSuggest,
  onCancel
}: {
  initialValue: Schema<"AssetContextValues">;
  contextSources: Schema<"AssetContextSources">;
  isSubmitting?: boolean;
  isSuggesting?: boolean;
  onSubmit: (payload: Schema<"AssetContextPatch">) => void;
  onSuggest: () => Promise<Schema<"AssetContextSuggestion">>;
  onCancel: () => void;
}) {
  const initialFormValues = useMemo(() => assetContextToFormValues(initialValue), [initialValue]);
  const [values, setValues] = useState(() => initialFormValues);
  const [suggestion, setSuggestion] = useState<Schema<"AssetContextSuggestion"> | null>(null);
  const validationError = validateAssetContextPatchValues(values);
  async function applySuggestion() {
    try {
      const result = await onSuggest();
      setValues(assetContextToFormValues(result.recommended_context));
      setSuggestion(result);
      toast.success("AI 추천값을 채웠습니다.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI 추천 실패");
    }
  }
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (validationError) {
          return;
        }
        const payload = buildAssetContextPatch(initialValue, values, contextSources);
        if (Object.keys(payload).length === 0) {
          toast.info("변경된 컨텍스트 값이 없습니다.");
          onCancel();
          return;
        }
        onSubmit(payload);
      }}
    >
      <fieldset className="form-fieldset" disabled={isSubmitting}>
        <div className="context-form-toolbar">
          <Button type="button" variant="secondary" disabled={isSuggesting} onClick={() => void applySuggestion()}>
            <Sparkles size={15} />{isSuggesting ? "추천 중" : "AI 추천"}
          </Button>
          {suggestion ? <span className="context-form-toolbar__meta">신뢰도 {(suggestion.confidence * 100).toFixed(0)}%</span> : null}
        </div>
        {suggestion ? <AiSuggestionTrace suggestion={suggestion} /> : null}
        <div className="form-grid">
          {(["sensitivity", "criticality"] as const).map((field) => (
            <Field key={field}>
              <FieldLabel>
                {contextFieldLabel(field)}
                {isContextFieldModified(field, initialFormValues, values) ? <span className="context-modified-badge">변경됨</span> : null}
              </FieldLabel>
              <FieldHint>{contextCurrentHint(field, initialValue, contextSources)}</FieldHint>
              <Select aria-label={`${contextFieldLabel(field)} 수정 값`} value={values[field]} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))}>
                <option value="">미지정</option>
                {["low", "medium", "high", "critical"].map((item) => (
                  <option key={item} value={item}>{levelLabel(item)}</option>
                ))}
              </Select>
            </Field>
          ))}
          <Field>
            <FieldLabel>
              {contextFieldLabel("exposure")}
              {isContextFieldModified("exposure", initialFormValues, values) ? <span className="context-modified-badge">변경됨</span> : null}
            </FieldLabel>
            <FieldHint>{contextCurrentHint("exposure", initialValue, contextSources)}</FieldHint>
            <Select aria-label="노출 범위 수정 값" value={values.exposure} onChange={(event) => setValues((current) => ({ ...current, exposure: event.target.value }))}>
              <option value="">미지정</option>
              {["public_internet", "dmz", "internal_network", "air_gapped"].map((item) => (
                <option key={item} value={item}>{exposureLabel(item)}</option>
              ))}
            </Select>
          </Field>
          <Field>
            <FieldLabel>
              {contextFieldLabel("lifespan_years")}
              {isContextFieldModified("lifespan_years", initialFormValues, values) ? <span className="context-modified-badge">변경됨</span> : null}
            </FieldLabel>
            <FieldHint>{contextCurrentHint("lifespan_years", initialValue, contextSources)}</FieldHint>
            <Input aria-label="보호 기간 수정 값" type="number" min="0" step="1" placeholder="미지정" value={values.lifespan_years} onChange={(event) => setValues((current) => ({ ...current, lifespan_years: event.target.value }))} />
          </Field>
          <Field className="is-wide">
            <FieldLabel>
              {contextFieldLabel("service_role")}
              {isContextFieldModified("service_role", initialFormValues, values) ? <span className="context-modified-badge">변경됨</span> : null}
            </FieldLabel>
            <FieldHint>{contextCurrentHint("service_role", initialValue, contextSources)}</FieldHint>
            <Input aria-label="서비스 역할 수정 값" placeholder="미지정" value={values.service_role} onChange={(event) => setValues((current) => ({ ...current, service_role: event.target.value }))} />
          </Field>
        </div>
        {validationError ? <div className="callout state-view--error" role="alert">{validationError}</div> : null}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onCancel}>취소</Button>
          <Button type="submit" variant="primary" disabled={Boolean(validationError)}>{isSubmitting ? "저장 중" : "저장"}</Button>
        </div>
      </fieldset>
    </form>
  );
}

function AiSuggestionTrace({ suggestion }: { suggestion: Schema<"AssetContextSuggestion"> }) {
  return (
    <details className="ai-trace-panel">
      <summary>AI 상세 Request / Response</summary>
      <div className="ai-trace-grid">
        <div>
          <div className="ai-trace-label">Request</div>
          <pre>{formatJsonPreview(suggestion.llm_trace.request)}</pre>
        </div>
        <div>
          <div className="ai-trace-label">Response</div>
          <pre>{formatAiResponsePreview(suggestion.llm_trace.response)}</pre>
        </div>
      </div>
    </details>
  );
}

type AssetContextField = keyof Schema<"AssetContextValues">;

function isContextFieldModified(
  field: AssetContextField,
  initialValues: Record<AssetContextField, string>,
  values: Record<AssetContextField, string>
) {
  return values[field] !== initialValues[field];
}

function contextCurrentHint(
  field: AssetContextField,
  effectiveValue: Schema<"AssetContextValues">,
  contextSources: Schema<"AssetContextSources">
) {
  return `현재 적용값: ${contextValueLabel(field, effectiveValue[field])} · 출처: ${contextSourceLabel(contextSources[field])}`;
}

function contextSourceLabel(source?: string | null) {
  const labels: Record<string, string> = {
    asset_override: "자산 재정의",
    target: "스캔 대상",
    heuristic: "기본값"
  };
  return source ? labels[source] ?? source : "-";
}

export function SnapshotDiffView({ id }: { id: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const otherId = searchParams.get("other") ? Number(searchParams.get("other")) : undefined;
  const [selectedBomRef, setSelectedBomRef] = useState<string | null>(null);
  const [showAllAssets, setShowAllAssets] = useState(false);
  const snapshots = useQuery({ queryKey: queryKeys.snapshots.all, queryFn: () => services.snapshots.list() });
  const diff = useQuery({
    queryKey: queryKeys.snapshots.diff(id, otherId),
    queryFn: () => services.snapshots.diff(id, otherId!),
    enabled: Boolean(otherId)
  });
  const previousAssets = useQuery({
    queryKey: queryKeys.snapshots.assets(otherId ?? 0, DIFF_ASSET_QUERY),
    queryFn: () => services.snapshots.assets(otherId!, DIFF_ASSET_QUERY),
    enabled: Boolean(otherId)
  });
  const currentAssets = useQuery({
    queryKey: queryKeys.snapshots.assets(id, DIFF_ASSET_QUERY),
    queryFn: () => services.snapshots.assets(id, DIFF_ASSET_QUERY),
    enabled: Boolean(otherId)
  });
  const previousAssetItems = previousAssets.data?.items ?? [];
  const currentAssetItems = currentAssets.data?.items ?? [];
  const previousAssetByBomRef = useMemo(() => indexAssetsByBomRef(previousAssetItems), [previousAssetItems]);
  const currentAssetByBomRef = useMemo(() => indexAssetsByBomRef(currentAssetItems), [currentAssetItems]);
  const diffIndex = useMemo(() => buildDiffIndex(diff.data), [diff.data]);
  const selectedPreviousAsset = selectedBomRef ? previousAssetByBomRef.get(selectedBomRef) ?? null : null;
  const selectedCurrentAsset = selectedBomRef ? currentAssetByBomRef.get(selectedBomRef) ?? null : null;
  const selectedModifiedAsset = selectedBomRef ? diffIndex.modified.get(selectedBomRef) ?? null : null;
  const isDiffLoading = diff.isLoading || previousAssets.isLoading || currentAssets.isLoading;
  const diffError = diff.error ?? previousAssets.error ?? currentAssets.error;
  const pairedRows = useMemo(
    () => buildDiffAssetPairs(diffIndex, showAllAssets, previousAssetItems, currentAssetItems),
    [currentAssetItems, diffIndex, previousAssetItems, showAllAssets]
  );

  useEffect(() => {
    if (!otherId || !diff.data) {
      setSelectedBomRef(null);
      return;
    }
    const selectedStatus = selectedBomRef ? getPairedDiffStatus(selectedBomRef, diffIndex) : null;
    if (
      selectedBomRef &&
      (previousAssetByBomRef.has(selectedBomRef) || currentAssetByBomRef.has(selectedBomRef)) &&
      (showAllAssets || selectedStatus !== "unchanged")
    ) {
      return;
    }
    setSelectedBomRef(getDefaultDiffSelection(diff.data, showAllAssets, previousAssetItems, currentAssetItems));
  }, [currentAssetByBomRef, currentAssetItems, diff.data, diffIndex, otherId, previousAssetByBomRef, previousAssetItems, selectedBomRef, showAllAssets]);

  return (
    <Section>
      <PageHeader title={`스냅샷 #${id} 비교`} description="기준 스냅샷과 비교할 이전 스냅샷을 선택합니다." />
      <Card>
        <CardContent>
          <div className="snapshot-diff-controls">
            <Field className="snapshot-diff-controls__select">
              <FieldLabel>비교 대상</FieldLabel>
              <Select
                value={otherId ?? ""}
                onChange={(event) => setSearchParams(event.target.value ? { other: event.target.value } : {})}
              >
                <option value="">스냅샷 선택</option>
                {(snapshots.data?.items ?? []).filter((snapshot) => snapshot.id !== id).map((snapshot) => (
                  <option key={snapshot.id} value={snapshot.id}>#{snapshot.id} · {formatDateTime(snapshot.created_at)}</option>
                ))}
              </Select>
            </Field>
            <label className="inline-actions snapshot-diff-controls__toggle">
              <Checkbox checked={showAllAssets} disabled={!otherId} onChange={(event) => setShowAllAssets(event.target.checked)} aria-label="전체보기" />
              <span>전체보기</span>
            </label>
          </div>
        </CardContent>
      </Card>
      {otherId && isDiffLoading ? <LoadingState /> : null}
      {otherId && diffError ? (
        <ErrorState
          error={diffError}
          onRetry={() => {
            void diff.refetch();
            void previousAssets.refetch();
            void currentAssets.refetch();
          }}
        />
      ) : null}
      {diff.data ? (
        <div className="section-stack">
          <div className="content-grid content-grid--4">
            <MetricCard label="추가" value={diff.data.added.length} />
            <MetricCard label="삭제" value={diff.data.removed.length} />
            <MetricCard label="변경" value={diff.data.modified.length} />
            <MetricCard label="회귀" value={diff.data.regressions.length} />
            <MetricCard label="동일" value={diff.data.unchanged_count} />
          </div>
          {diff.data.regressions.length > 0 ? <DiffRegressionReport regressions={diff.data.regressions} /> : null}
          <SelectedAssetComparison
            snapshotA={diff.data.snapshot_a}
            snapshotB={diff.data.snapshot_b}
            selectedBomRef={selectedBomRef}
            previousAsset={selectedPreviousAsset}
            currentAsset={selectedCurrentAsset}
            modifiedAsset={selectedModifiedAsset}
            status={selectedBomRef ? getPairedDiffStatus(selectedBomRef, diffIndex) : "unchanged"}
            currentIsLatest
          />
          <div className="snapshot-diff-grid">
            <DiffAssetTable
              title={`스냅샷 #${diff.data.snapshot_a}`}
              side="previous"
              rows={pairedRows}
              diffIndex={diffIndex}
              selectedBomRef={selectedBomRef}
              onSelect={setSelectedBomRef}
            />
            <DiffAssetTable
              title={`스냅샷 #${diff.data.snapshot_b}`}
              latest
              side="current"
              rows={pairedRows}
              diffIndex={diffIndex}
              selectedBomRef={selectedBomRef}
              onSelect={setSelectedBomRef}
            />
          </div>
        </div>
      ) : null}
    </Section>
  );
}

const DIFF_ASSET_QUERY = { limit: 100, sort: "name" } as const;

type DiffAsset = Schema<"AssetListItem">;
type DiffRegression = Schema<"CbomDiffRegression">;
type DiffAssetStatus = "added" | "removed" | "modified" | "unchanged";
type DiffSide = "previous" | "current";

type DiffAssetPair = {
  bom_ref: string;
  status: DiffAssetStatus;
  previous: DiffAsset | null;
  current: DiffAsset | null;
};

type DiffIndex = {
  added: Set<string>;
  removed: Set<string>;
  modified: Map<string, Schema<"CbomDiffModifiedAsset">>;
};

function DiffRegressionReport({ regressions }: { regressions: DiffRegression[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>회귀 감지</CardTitle>
      </CardHeader>
      <CardContent>
        <DataTable
          items={regressions}
          getRowKey={(item, index) => `${item.kind}:${item.bom_ref}:${index}`}
          empty={<EmptyState title="감지된 회귀가 없습니다" />}
          columns={[
            { key: "severity", header: "심각도", render: (item) => <RegressionSeverityBadge severity={item.severity} /> },
            { key: "kind", header: "유형", render: (item) => regressionKindLabel(item.kind) },
            { key: "asset", header: "자산", render: (item) => <span className="mono">{item.bom_ref}</span> },
            { key: "before", header: "이전", render: (item) => regressionStateLabel(item.before) },
            { key: "after", header: "현재", render: (item) => regressionStateLabel(item.after) },
            { key: "message", header: "설명", render: (item) => regressionMessageLabel(item.message) }
          ]}
        />
      </CardContent>
    </Card>
  );
}

function DiffAssetTable({
  title,
  latest = false,
  side,
  rows,
  diffIndex,
  selectedBomRef,
  onSelect
}: {
  title: string;
  latest?: boolean;
  side: DiffSide;
  rows: DiffAssetPair[];
  diffIndex: DiffIndex;
  selectedBomRef: string | null;
  onSelect: (bomRef: string) => void;
}) {
  return (
    <Card className="snapshot-diff-table-card">
      <CardHeader>
        <CardTitle>
          <span className="snapshot-diff-title">
            {title}
            {latest ? <Badge tone="purple">최신</Badge> : null}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <DataTable
          items={rows}
          getRowKey={(row) => row.bom_ref}
          rowClassName={(row) => (row.bom_ref === selectedBomRef ? "is-selected" : undefined)}
          onRowClick={(row) => onSelect(row.bom_ref)}
          empty={<EmptyState title="자산이 없습니다" />}
          columns={[
            { key: "status", header: "상태", render: (row) => <DiffSideStatus row={row} side={side} diffIndex={diffIndex} /> },
            {
              key: "bom_ref",
              header: "BOM 참조",
              render: (row) => <DiffSideBomRef row={row} side={side} selectedBomRef={selectedBomRef} onSelect={onSelect} />
            },
            { key: "name", header: "이름", render: (row) => getDiffPairAsset(row, side)?.name ?? <span className="muted">-</span> },
            { key: "type", header: "타입", render: (row) => assetTypeLabel(getDiffPairAsset(row, side)?.asset_type) }
          ]}
        />
      </CardContent>
    </Card>
  );
}

function DiffSideStatus({ row, side, diffIndex }: { row: DiffAssetPair; side: DiffSide; diffIndex: DiffIndex }) {
  const asset = getDiffPairAsset(row, side);
  if (!asset) {
    return <span className="muted">-</span>;
  }
  return <DiffStatusBadge status={getSideDiffStatus(row.bom_ref, side, diffIndex)} />;
}

function DiffSideBomRef({
  row,
  side,
  selectedBomRef,
  onSelect
}: {
  row: DiffAssetPair;
  side: DiffSide;
  selectedBomRef: string | null;
  onSelect: (bomRef: string) => void;
}) {
  if (!getDiffPairAsset(row, side)) {
    return <span className="muted">-</span>;
  }
  return (
    <button
      className={row.bom_ref === selectedBomRef ? "link-button diff-select-button is-selected" : "link-button diff-select-button"}
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelect(row.bom_ref);
      }}
    >
      {row.bom_ref}
    </button>
  );
}

function SelectedAssetComparison({
  snapshotA,
  snapshotB,
  selectedBomRef,
  previousAsset,
  currentAsset,
  modifiedAsset,
  status,
  currentIsLatest = false
}: {
  snapshotA: number;
  snapshotB: number;
  selectedBomRef: string | null;
  previousAsset: DiffAsset | null;
  currentAsset: DiffAsset | null;
  modifiedAsset: Schema<"CbomDiffModifiedAsset"> | null;
  status: DiffAssetStatus;
  currentIsLatest?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>선택 자산 비교</CardTitle>
      </CardHeader>
      <CardContent>
        {!selectedBomRef ? <EmptyState title="비교할 자산을 선택하세요" description="좌측 또는 우측 테이블에서 BOM 참조를 선택합니다." /> : null}
        {selectedBomRef ? (
          <div className="snapshot-diff-detail">
            <div className="snapshot-diff-detail__header">
              <span className="mono">{selectedBomRef}</span>
              <DiffStatusBadge status={status} />
            </div>
            <div className="snapshot-diff-detail__assets">
              <DiffAssetSummary title={`스냅샷 #${snapshotA}`} asset={previousAsset} emptyLabel="이전 스냅샷에 없음" />
              <DiffAssetSummary title={`스냅샷 #${snapshotB}`} latest={currentIsLatest} asset={currentAsset} emptyLabel="현재 스냅샷에 없음" />
            </div>
            <div className="snapshot-diff-detail__changes">
              <h3>변경 필드</h3>
              <DiffFieldChanges status={status} snapshotA={snapshotA} snapshotB={snapshotB} modifiedAsset={modifiedAsset} />
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DiffAssetSummary({ title, latest = false, asset, emptyLabel }: { title: string; latest?: boolean; asset: DiffAsset | null; emptyLabel: string }) {
  return (
    <div className="snapshot-diff-asset-summary">
      <h3>
        <span className="snapshot-diff-title">
          {title}
          {latest ? <Badge tone="purple">최신</Badge> : null}
        </span>
      </h3>
      {asset ? (
        <dl className="detail-list">
          <div><dt>이름</dt><dd>{asset.name}</dd></div>
          <div><dt>타입</dt><dd>{assetTypeLabel(asset.asset_type)}</dd></div>
          <div><dt>스캔 대상</dt><dd>{asset.target_label ?? (asset.target_id ? `#${asset.target_id}` : "-")}</dd></div>
          <div><dt>위험도</dt><dd>{asset.risk ? <RiskTierBadge tier={asset.risk.tier} /> : "-"}</dd></div>
          <div><dt>알고리즘</dt><dd>{formatDiffValue(asset.summary.algorithm)}</dd></div>
          <div><dt>패밀리</dt><dd>{formatDiffValue(asset.summary.algorithm_family)}</dd></div>
        </dl>
      ) : (
        <EmptyState title={emptyLabel} />
      )}
    </div>
  );
}

function DiffFieldChanges({
  status,
  snapshotA,
  snapshotB,
  modifiedAsset
}: {
  status: DiffAssetStatus;
  snapshotA: number;
  snapshotB: number;
  modifiedAsset: Schema<"CbomDiffModifiedAsset"> | null;
}) {
  if (status === "added") {
    return <span>스냅샷 #{snapshotB}에만 존재합니다.</span>;
  }
  if (status === "removed") {
    return <span>스냅샷 #{snapshotA}에만 존재합니다.</span>;
  }
  if (status === "unchanged") {
    return <span>선택한 자산의 비교 대상 필드는 동일합니다.</span>;
  }
  return <DiffChangeSummary fieldChanges={modifiedAsset?.field_changes ?? {}} />;
}

function DiffStatusBadge({ status }: { status: DiffAssetStatus }) {
  if (status === "added") {
    return <Badge tone="green">추가</Badge>;
  }
  if (status === "removed") {
    return <Badge tone="red">삭제</Badge>;
  }
  if (status === "modified") {
    return <Badge tone="blue">변경</Badge>;
  }
  return <Badge tone="neutral">동일</Badge>;
}

function RegressionSeverityBadge({ severity }: { severity: DiffRegression["severity"] }) {
  return <Badge tone={severity === "high" ? "red" : "yellow"}>{severity === "high" ? "높음" : "중간"}</Badge>;
}

function DiffChangeSummary({ fieldChanges }: { fieldChanges: Record<string, unknown[]> }) {
  const changes = Object.entries(fieldChanges);
  if (!changes.length) {
    return <span>-</span>;
  }
  return (
    <div className="diff-change-list">
      {changes.map(([field, values]) => (
        <div key={field} className="diff-change-list__item">
          <span className="diff-change-list__field">{diffFieldLabel(field)}</span>
          <span className="diff-change-list__value">{formatDiffFieldValue(field, values[0])}</span>
          <span className="diff-change-list__arrow">→</span>
          <span className="diff-change-list__value">{formatDiffFieldValue(field, values[1])}</span>
        </div>
      ))}
    </div>
  );
}

function buildDiffIndex(diff?: Schema<"CbomDiff">): DiffIndex {
  return {
    added: new Set(diff?.added.map((asset) => asset.bom_ref) ?? []),
    removed: new Set(diff?.removed.map((asset) => asset.bom_ref) ?? []),
    modified: new Map(diff?.modified.map((asset) => [asset.bom_ref, asset]) ?? [])
  };
}

function indexAssetsByBomRef(assets: DiffAsset[]) {
  return new Map(assets.map((asset) => [asset.bom_ref, asset]));
}

function buildDiffAssetPairs(diffIndex: DiffIndex, showAllAssets: boolean, previousAssets: DiffAsset[], currentAssets: DiffAsset[]): DiffAssetPair[] {
  const previousByBomRef = indexAssetsByBomRef(previousAssets);
  const currentByBomRef = indexAssetsByBomRef(currentAssets);
  const bomRefs = new Set<string>();
  for (const asset of previousAssets) {
    bomRefs.add(asset.bom_ref);
  }
  for (const asset of currentAssets) {
    bomRefs.add(asset.bom_ref);
  }

  return [...bomRefs]
    .map((bomRef) => ({
      bom_ref: bomRef,
      status: getPairedDiffStatus(bomRef, diffIndex),
      previous: previousByBomRef.get(bomRef) ?? null,
      current: currentByBomRef.get(bomRef) ?? null
    }))
    .filter((row) => showAllAssets || row.status !== "unchanged")
    .sort(compareDiffAssetPairs);
}

function compareDiffAssetPairs(left: DiffAssetPair, right: DiffAssetPair) {
  const statusOrder: Record<DiffAssetStatus, number> = { modified: 0, added: 1, removed: 2, unchanged: 3 };
  const statusDelta = statusOrder[left.status] - statusOrder[right.status];
  if (statusDelta !== 0) {
    return statusDelta;
  }
  return left.bom_ref.localeCompare(right.bom_ref);
}

function getDiffPairAsset(row: DiffAssetPair, side: DiffSide) {
  return side === "previous" ? row.previous : row.current;
}

function getSideDiffStatus(bomRef: string, side: DiffSide, diffIndex: DiffIndex): DiffAssetStatus {
  if (side === "previous" && diffIndex.removed.has(bomRef)) {
    return "removed";
  }
  if (side === "current" && diffIndex.added.has(bomRef)) {
    return "added";
  }
  if (diffIndex.modified.has(bomRef)) {
    return "modified";
  }
  return "unchanged";
}

function getPairedDiffStatus(bomRef: string, diffIndex: DiffIndex): DiffAssetStatus {
  if (diffIndex.added.has(bomRef)) {
    return "added";
  }
  if (diffIndex.removed.has(bomRef)) {
    return "removed";
  }
  if (diffIndex.modified.has(bomRef)) {
    return "modified";
  }
  return "unchanged";
}

function getDefaultDiffSelection(diff: Schema<"CbomDiff">, showAllAssets: boolean, previousAssets: DiffAsset[], currentAssets: DiffAsset[]) {
  return (
    diff.modified[0]?.bom_ref ??
    diff.added[0]?.bom_ref ??
    diff.removed[0]?.bom_ref ??
    (showAllAssets ? currentAssets[0]?.bom_ref ?? previousAssets[0]?.bom_ref : null) ??
    null
  );
}

function formatDiffValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function formatDiffFieldValue(field: string, value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (field === "asset_class") {
    return assetClassLabel(String(value));
  }
  if (field === "asset_type") {
    return assetTypeLabel(String(value));
  }
  if (field === "risk_tier") {
    return riskTierLabel(String(value));
  }
  return contextValueLabel(field, value) === "-" ? formatDiffValue(value) : contextValueLabel(field, value);
}

function regressionKindLabel(kind: DiffRegression["kind"]) {
  const labels: Record<DiffRegression["kind"], string> = {
    asset_removed: "자산 누락",
    algorithm_removed: "알고리즘 삭제",
    algorithm_downgrade: "알고리즘 다운그레이드"
  };
  return labels[kind];
}

function regressionMessageLabel(message: string) {
  const labels: Record<string, string> = {
    "Asset is missing from the post-migration snapshot.": "전환 후 스냅샷에서 자산이 사라졌습니다.",
    "Algorithm metadata was removed from the post-migration snapshot.": "전환 후 스냅샷에서 알고리즘 정보가 삭제되었습니다.",
    "Algorithm strength decreased in the post-migration snapshot.": "전환 후 스냅샷에서 알고리즘 강도가 낮아졌습니다."
  };
  return labels[message] ?? message;
}

function regressionStateLabel(state: DiffRegression["before"]) {
  if (!state) {
    return "-";
  }
  const algorithm = typeof state.algorithm === "string" && state.algorithm ? state.algorithm : "-";
  const family = typeof state.algorithm_family === "string" && state.algorithm_family ? state.algorithm_family : "";
  return family ? `${algorithm} (${family})` : algorithm;
}

function diffFieldLabel(field: string) {
  const labels: Record<string, string> = {
    name: "이름",
    asset_class: "분류",
    asset_type: "타입",
    risk_score: "위험 점수",
    risk_tier: "위험 등급",
    algorithm: "알고리즘",
    algorithm_family: "알고리즘 패밀리",
    target_label: "스캔 대상",
    target_id: "스캔 대상 ID"
  };
  return labels[field] ?? contextFieldLabel(field);
}
