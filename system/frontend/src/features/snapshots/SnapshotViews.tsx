import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { RiskTierBadge } from "../../components/common/Badges";
import { JsonPreview } from "../../components/common/JsonPreview";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { MetricCard } from "../../components/charts/MetricCard";
import { AssetGraph } from "../../components/graph/AssetGraph";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { parseRiskTierParam, riskTierOptions } from "../../domain/filterOptions";
import { isTerminalJobStatus } from "../../domain/jobStatus";
import { formatDateTime, formatNumber, formatScore } from "../../lib/format";
import { downloadJson } from "../../lib/download";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import {
  assetContextEnabledFields,
  assetContextToFormValues,
  buildAssetContextPatch,
  validateAssetContextPatchValues,
  type AssetContextEnabledFields
} from "./assetContextPatch";

export function SnapshotsView() {
  const navigate = useNavigate();
  const snapshots = useQuery({
    queryKey: queryKeys.snapshots.all,
    queryFn: () => services.snapshots.list()
  });

  return (
    <Section>
      <PageHeader title="식별 자산" description="스캔 결과로 식별된 암호자산 스냅샷을 조회합니다." />
      {snapshots.isLoading ? <LoadingState /> : null}
      {snapshots.isError ? <ErrorState error={snapshots.error} onRetry={() => void snapshots.refetch()} /> : null}
      {snapshots.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={snapshots.data.items}
              getRowKey={(snapshot) => snapshot.id}
              empty={<EmptyState title="식별 자산 스냅샷이 없습니다" description="스캔이 완료되면 이곳에 표시됩니다." />}
              columns={[
                { key: "id", header: "스냅샷", render: (snapshot) => <button className="link-button" onClick={() => navigate(`/snapshots/${snapshot.id}`)}>#{snapshot.id}</button> },
                { key: "serial", header: "Serial", render: (snapshot) => <span className="mono">{snapshot.serial_number}</span> },
                { key: "assets", header: "식별 자산", render: (snapshot) => formatNumber(snapshot.asset_count) },
                { key: "critical", header: "Critical", render: (snapshot) => snapshot.summary.by_tier?.CRITICAL ?? 0 },
                { key: "created", header: "Created", render: (snapshot) => formatDateTime(snapshot.created_at) }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}
    </Section>
  );
}

export function SnapshotDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [exportingCbom, setExportingCbom] = useState(false);
  const tier = parseRiskTierParam(searchParams.get("tier"));
  const q = searchParams.get("q") ?? "";
  const snapshot = useQuery({
    queryKey: queryKeys.snapshots.detail(id),
    queryFn: () => services.snapshots.get(id)
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
        title={`식별 자산 #${snapshot.data.id}`}
        description={formatDateTime(snapshot.data.created_at)}
        actions={
          <>
            <Button type="button" disabled={exportingCbom} onClick={() => void exportCbom()}>
              <Download size={15} />CBOM JSON
            </Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/diff`)}>Diff</Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/risk`)}>Risk</Button>
            <Button type="button" onClick={() => navigate(`/snapshots/${id}/migration`)}>Migration</Button>
          </>
        }
      />
      <div className="content-grid content-grid--4">
        <MetricCard label="식별 자산" value={snapshot.data.asset_count} />
        <MetricCard label="Critical" value={snapshot.data.summary.by_tier?.CRITICAL ?? 0} />
        <MetricCard label="High" value={snapshot.data.summary.by_tier?.HIGH ?? 0} />
        <MetricCard label="Validation Errors" value={snapshot.data.validation_errors.length} />
      </div>
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Input aria-label="Asset search" value={q} onChange={(event) => setSearchParams({ ...(tier ? { tier } : {}), ...(event.target.value ? { q: event.target.value } : {}) })} placeholder="asset search" />
              <Select aria-label="Asset risk tier filter" value={tier ?? ""} onChange={(event) => setSearchParams({ ...(event.target.value ? { tier: event.target.value } : {}), ...(q ? { q } : {}) })}>
                <option value="">All tiers</option>
                {riskTierOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
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
                { key: "name", header: "Name", render: (asset) => <button className="link-button" onClick={() => navigate(`/snapshots/${id}/assets/${asset.id}`)}>{asset.name}</button> },
                { key: "class", header: "Class", render: (asset) => asset.asset_class },
                { key: "type", header: "Type", render: (asset) => asset.asset_type },
                { key: "target", header: "스캔 대상", render: (asset) => asset.target_label ?? (asset.target_id ? `#${asset.target_id}` : "-") },
                { key: "score", header: "Score", render: (asset) => formatScore(asset.risk?.score) },
                { key: "tier", header: "Tier", render: (asset) => <RiskTierBadge tier={asset.risk?.tier} /> }
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
  const qualitative = useMutation({
    mutationFn: () => services.assets.qualitative(assetId),
    onSuccess: async () => {
      toast.success("정성 평가를 생성했습니다.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "정성 평가 실패")
  });
  const patchContext = useMutation({
    mutationFn: (payload: Schema<"AssetContextPatch">) => services.assets.patchContext(assetId, payload),
    onSuccess: async (result) => {
      toast.success(`저장했습니다. Recompute job #${result.recompute_job_id}`);
      setEditing(false);
      setRecomputeJobId(result.recompute_job_id);
      trackJob(result.recompute_job_id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(snapshotId) });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "저장 실패")
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
      toast.success("Asset context recompute 완료");
      setRecomputeJobId(null);
    }
    if (recomputeJob.data?.status && isTerminalJobStatus(recomputeJob.data.status) && recomputeJob.data.status !== "COMPLETED") {
      toast.error(recomputeJob.data.status === "CANCELLED" ? "Asset context recompute 취소됨" : "Asset context recompute 실패");
      setRecomputeJobId(null);
    }
  }, [assetId, queryClient, recomputeJob.data?.status, snapshotId]);

  if (asset.isLoading) {
    return <LoadingState />;
  }
  if (asset.isError || !asset.data) {
    return <ErrorState error={asset.error} onRetry={() => void asset.refetch()} />;
  }

  const dependencies = asset.data.dependencies ?? { dependsOn: [], dependedBy: [] };

  return (
    <Section>
      <PageHeader
        title={asset.data.name}
        description={`${asset.data.asset_class} · ${asset.data.asset_type}`}
        actions={
          <>
            <Button type="button" disabled={qualitative.isPending} onClick={() => !qualitative.isPending && qualitative.mutate()}>
              {qualitative.isPending ? "평가 중" : "정성 평가"}
            </Button>
            <Button type="button" variant="primary" onClick={() => setEditing((value) => !value)}>
              <Save size={15} />컨텍스트 수정
            </Button>
          </>
        }
      />
      {recomputeJob.data ? <div className="callout" role="status" aria-live="polite">Recompute #{recomputeJob.data.id}: {recomputeJob.data.status}</div> : null}
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>자산 정보</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>ID</dt><dd>#{asset.data.id}</dd></div>
              <div><dt>BOM Ref</dt><dd className="mono">{asset.data.bom_ref ?? "-"}</dd></div>
              <div><dt>스캔 대상</dt><dd>{asset.data.target?.host ?? "-"}</dd></div>
              <div><dt>Risk</dt><dd>{asset.data.risk ? <RiskTierBadge tier={asset.data.risk.tier} /> : "-"}</dd></div>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Effective Context</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              {Object.entries(asset.data.effective_context).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{String(value ?? "-")}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>
      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>Context Override</CardTitle>
          </CardHeader>
          <CardContent>
            <AssetContextForm
              initialValue={asset.data.context_override}
              isSubmitting={patchContext.isPending}
              onCancel={() => setEditing(false)}
              onSubmit={(payload) => patchContext.mutate(payload)}
            />
          </CardContent>
        </Card>
      ) : null}
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>Dependencies</CardTitle>
          </CardHeader>
          <CardContent>
            <AssetGraph dependencies={dependencies} onAssetSelect={(nextAssetId) => navigate(`/snapshots/${snapshotId}/assets/${nextAssetId}`)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Qualitative Assessment</CardTitle>
          </CardHeader>
          <CardContent>
            {asset.data.qualitative ? (
              <div className="section-stack">
                <strong>{asset.data.qualitative.summary}</strong>
                <p>{asset.data.qualitative.migration_recommendation}</p>
                <span className="muted">confidence {asset.data.qualitative.confidence}</span>
              </div>
            ) : (
              <EmptyState title="정성 평가가 없습니다" />
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Properties</CardTitle>
        </CardHeader>
        <CardContent>
          <JsonPreview value={{ crypto_properties: asset.data.crypto_properties, properties: asset.data.properties, history: asset.data.history }} />
        </CardContent>
      </Card>
    </Section>
  );
}

function AssetContextForm({
  initialValue,
  isSubmitting = false,
  onSubmit,
  onCancel
}: {
  initialValue: Schema<"AssetContextValues">;
  isSubmitting?: boolean;
  onSubmit: (payload: Schema<"AssetContextPatch">) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState(() => assetContextToFormValues(initialValue));
  const [enabled, setEnabled] = useState<AssetContextEnabledFields>(() => assetContextEnabledFields(initialValue));
  const validationError = validateAssetContextPatchValues(values, enabled);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (validationError) {
          return;
        }
        onSubmit(buildAssetContextPatch(initialValue, values, enabled));
      }}
    >
      <fieldset className="form-fieldset" disabled={isSubmitting}>
        <div className="form-grid">
          {(["sensitivity", "criticality"] as const).map((field) => (
            <Field key={field}>
              <FieldLabel>{field}</FieldLabel>
              <span className="inline-actions">
                <Checkbox
                  checked={enabled[field]}
                  onChange={(event) => setEnabled((current) => ({ ...current, [field]: event.target.checked }))}
                  aria-label={`${field} override 사용`}
                />
              <Select aria-label={`${field} override value`} disabled={!enabled[field]} value={values[field]} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))}>
                  {["", "low", "medium", "high", "critical"].map((item) => (
                    <option key={item || "empty"} value={item}>{item || "clear"}</option>
                  ))}
                </Select>
              </span>
            </Field>
          ))}
          <Field>
            <FieldLabel>Exposure</FieldLabel>
            <span className="inline-actions">
              <Checkbox
                checked={enabled.exposure}
                onChange={(event) => setEnabled((current) => ({ ...current, exposure: event.target.checked }))}
                aria-label="exposure override 사용"
              />
              <Select aria-label="exposure override value" disabled={!enabled.exposure} value={values.exposure} onChange={(event) => setValues((current) => ({ ...current, exposure: event.target.value }))}>
                {["", "public_internet", "dmz", "internal_network", "air_gapped"].map((item) => (
                  <option key={item || "empty"} value={item}>{item || "clear"}</option>
                ))}
              </Select>
            </span>
          </Field>
          <Field>
            <FieldLabel>Lifespan Years</FieldLabel>
            <span className="inline-actions">
              <Checkbox
                checked={enabled.lifespan_years}
                onChange={(event) => setEnabled((current) => ({ ...current, lifespan_years: event.target.checked }))}
                aria-label="lifespan_years override 사용"
              />
              <Input aria-label="lifespan_years override value" type="number" min="0" step="1" disabled={!enabled.lifespan_years} value={values.lifespan_years} onChange={(event) => setValues((current) => ({ ...current, lifespan_years: event.target.value }))} />
            </span>
          </Field>
          <Field className="is-wide">
            <FieldLabel>Service Role</FieldLabel>
            <span className="inline-actions">
              <Checkbox
                checked={enabled.service_role}
                onChange={(event) => setEnabled((current) => ({ ...current, service_role: event.target.checked }))}
                aria-label="service_role override 사용"
              />
              <Input aria-label="service_role override value" disabled={!enabled.service_role} value={values.service_role} onChange={(event) => setValues((current) => ({ ...current, service_role: event.target.value }))} />
            </span>
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

export function SnapshotDiffView({ id }: { id: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const otherId = searchParams.get("other") ? Number(searchParams.get("other")) : undefined;
  const snapshots = useQuery({ queryKey: queryKeys.snapshots.all, queryFn: () => services.snapshots.list() });
  const diff = useQuery({
    queryKey: queryKeys.snapshots.diff(id, otherId),
    queryFn: () => services.snapshots.diff(id, otherId!),
    enabled: Boolean(otherId)
  });
  return (
    <Section>
      <PageHeader title={`Snapshot #${id} Diff`} description="기준 스냅샷과 비교할 이전 스냅샷을 선택합니다." />
      <Card>
        <CardContent>
          <Field>
            <FieldLabel>Compare with</FieldLabel>
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
        </CardContent>
      </Card>
      {diff.isLoading ? <LoadingState /> : null}
      {diff.isError ? <ErrorState error={diff.error} onRetry={() => void diff.refetch()} /> : null}
      {diff.data ? (
        <div className="content-grid content-grid--4">
          <MetricCard label="Added" value={diff.data.added.length} />
          <MetricCard label="Removed" value={diff.data.removed.length} />
          <MetricCard label="Modified" value={diff.data.modified.length} />
          <MetricCard label="Unchanged" value={diff.data.unchanged_count} />
          <Card className="is-wide">
            <CardHeader><CardTitle>Raw Diff</CardTitle></CardHeader>
            <CardContent><JsonPreview value={diff.data} /></CardContent>
          </Card>
        </div>
      ) : null}
    </Section>
  );
}
