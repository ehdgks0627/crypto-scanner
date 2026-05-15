import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { RiskWeightsInput, Schema } from "../../api/types";
import { DhsPriorityBadge, RiskTierBadge } from "../../components/common/Badges";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { assetTypeLabel, riskTierLabel, statusLabel } from "../../domain/displayLabels";
import { parseRiskTierParam, riskTierOptions } from "../../domain/filterOptions";
import { isActiveJobStatus } from "../../domain/jobStatus";
import { areRiskWeightsValid, updateRiskWeight } from "../../domain/riskWeights";
import { formatDateTime, formatOptionalScore, formatScore } from "../../lib/format";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import { RiskFormulaHelp, riskWeightLabel } from "./RiskFormulaHelp";

export function RiskAssessmentView({ snapshotId }: { snapshotId: number }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const trackJob = useJobWatchStore((state) => state.trackJob);
  const tier = parseRiskTierParam(searchParams.get("tier"));
  const [weights, setWeights] = useState<RiskWeightsInput>({ wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 });
  const [persist, setPersist] = useState(false);
  const [recomputeRequest, setRecomputeRequest] = useState<{ id: number; persist: boolean } | null>(null);
  const riskWeights = useQuery({
    queryKey: queryKeys.risk.weights,
    queryFn: () => services.risk.weights()
  });
  const risks = useQuery({
    queryKey: queryKeys.risk.list(snapshotId, { tier }),
    queryFn: () => services.risk.list(snapshotId, { tier: tier ? [tier] : undefined })
  });
  const topRisks = useQuery({
    queryKey: queryKeys.risk.top(snapshotId),
    queryFn: () => services.risk.top(snapshotId)
  });
  const saveWeights = useMutation({
    mutationFn: () => services.risk.putWeights(weights),
    onSuccess: async () => {
      toast.success("기본 가중치를 저장했습니다.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.risk.weights });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "가중치 저장 실패")
  });
  const recompute = useMutation({
    mutationFn: () => services.risk.recompute(snapshotId, weights, persist),
    onSuccess: (job) => {
      setRecomputeRequest({ id: job.id, persist });
      trackJob(job.id);
      toast.success(`재계산 작업 #${job.id} 생성`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "재계산 요청 실패")
  });
  const recomputeJob = useQuery({
    queryKey: recomputeRequest ? queryKeys.jobs.detail(recomputeRequest.id) : ["jobs", "detail", "none"],
    queryFn: () => services.jobs.get(recomputeRequest!.id),
    enabled: Boolean(recomputeRequest),
    refetchInterval: (query) => (query.state.data?.status === "PENDING" || query.state.data?.status === "RUNNING" ? 3_000 : false)
  });
  const weightsReady = Boolean(riskWeights.data) && !riskWeights.isError && areRiskWeightsValid(weights);
  const isRecomputePolling = Boolean(recomputeRequest) && (!recomputeJob.data || isActiveJobStatus(recomputeJob.data.status));

  useEffect(() => {
    if (riskWeights.data) {
      setWeights({
        wA: riskWeights.data.wA,
        wD: riskWeights.data.wD,
        wE: riskWeights.data.wE,
        wL: riskWeights.data.wL,
        wC: riskWeights.data.wC
      });
    }
  }, [riskWeights.data]);

  useEffect(() => {
    if (recomputeJob.data?.status === "COMPLETED") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.detail(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.listPrefix(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.top(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(snapshotId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.migration.planPrefix(snapshotId) });
      if (recomputeRequest?.persist) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.risk.weights });
      }
      toast.success("위험평가 재계산 완료");
      setRecomputeRequest(null);
    }
    if (recomputeJob.data?.status === "FAILED" || recomputeJob.data?.status === "CANCELLED") {
      toast.error(recomputeJob.data.status === "FAILED" ? "위험평가 재계산 실패" : "위험평가 재계산 취소됨");
      setRecomputeRequest(null);
    }
  }, [queryClient, recomputeJob.data?.status, recomputeRequest?.persist, snapshotId]);

  return (
    <Section>
      <PageHeader
        title={`스냅샷 #${snapshotId} 위험평가`}
        description="위험 점수와 가중치를 조정하고 재계산합니다."
        actions={
          <>
            <Button type="button" disabled={!weightsReady || saveWeights.isPending} onClick={() => saveWeights.mutate()}>
              <Save size={15} />가중치 저장
            </Button>
            <Button type="button" variant="primary" disabled={!weightsReady || recompute.isPending || isRecomputePolling} onClick={() => recompute.mutate()}>
              <RefreshCw size={15} />재계산
            </Button>
          </>
        }
      />
      <div className="split-pane">
        <Card>
          <CardHeader>
            <CardTitle>상위 위험 자산</CardTitle>
          </CardHeader>
          <CardContent>
            {topRisks.isLoading ? <LoadingState /> : null}
            {topRisks.isError ? <ErrorState error={topRisks.error} onRetry={() => void topRisks.refetch()} /> : null}
            {topRisks.data ? <RiskTable risks={topRisks.data.items} onAssetClick={(assetId) => navigate(`/snapshots/${snapshotId}/assets/${assetId}`)} /> : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>위험 가중치</CardTitle>
          </CardHeader>
          <CardContent>
            {riskWeights.isLoading ? <LoadingState /> : null}
            {riskWeights.isError ? <ErrorState error={riskWeights.error} onRetry={() => void riskWeights.refetch()} /> : null}
            {riskWeights.data ? <span className="muted">업데이트 {formatDateTime(riskWeights.data.updated_at)}</span> : null}
            {recomputeJob.data ? <p className="muted" role="status" aria-live="polite">재계산 #{recomputeJob.data.id}: {statusLabel(recomputeJob.data.status)}</p> : null}
            <RiskFormulaHelp />
            {!areRiskWeightsValid(weights) ? <div className="callout state-view--error" role="alert">가중치는 0.5부터 2.0 사이 숫자여야 합니다.</div> : null}
            <div className="form-grid risk-weight-grid" role="group" aria-label="위험 가중치 입력">
              {(Object.keys(weights) as Array<keyof RiskWeightsInput>).map((key) => (
                <Field key={key}>
                  <FieldLabel>{riskWeightLabel(key)}</FieldLabel>
                  <Input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="2"
                    value={Number.isNaN(weights[key]) ? "" : weights[key]}
                    onChange={(event) => setWeights((current) => updateRiskWeight(current, key, event.target.value))}
                  />
                </Field>
              ))}
            </div>
            <Field className="risk-weight-persist">
              <FieldLabel>기본값 저장</FieldLabel>
              <span className="inline-actions">
                <Checkbox checked={persist} onChange={(event) => setPersist(event.target.checked)} />
                <span>재계산 가중치를 기본값으로 저장</span>
              </span>
            </Field>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>위험 점수</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="toolbar">
            <Select
              aria-label="위험도 등급 필터"
              value={tier}
              onChange={(event) => setSearchParams(event.target.value ? { tier: event.target.value } : {})}
            >
              <option value="">전체 등급</option>
              {riskTierOptions.map((item) => (
                <option key={item} value={item}>{riskTierLabel(item)}</option>
              ))}
            </Select>
          </div>
          {risks.isLoading ? <LoadingState /> : null}
          {risks.isError ? <ErrorState error={risks.error} onRetry={() => void risks.refetch()} /> : null}
          {risks.data ? <RiskTable risks={risks.data.items} onAssetClick={(assetId) => navigate(`/snapshots/${snapshotId}/assets/${assetId}`)} /> : null}
        </CardContent>
      </Card>
    </Section>
  );
}

function RiskTable({ risks, onAssetClick }: { risks: Schema<"RiskScore">[]; onAssetClick?: (assetId: number) => void }) {
  return (
    <DataTable
      items={risks}
      getRowKey={(risk, index) => `${risk.asset_id ?? index}`}
      empty={<EmptyState title="위험 점수가 없습니다" />}
      columns={[
        {
          key: "asset",
          header: "자산",
          render: (risk) =>
            onAssetClick ? (
              <button className="link-button" type="button" onClick={() => onAssetClick(risk.asset_id)}>
                {risk.asset_name ?? `#${risk.asset_id}`}
              </button>
            ) : (
              risk.asset_name ?? `#${risk.asset_id}`
            )
        },
        { key: "type", header: "타입", render: (risk) => assetTypeLabel(risk.asset_type) },
        { key: "score", header: "점수", render: (risk) => formatScore(risk.score) },
        { key: "tier", header: "등급", render: (risk) => <RiskTierBadge tier={risk.tier} /> },
        { key: "dhs-score", header: "DHS 점수", render: (risk) => formatOptionalScore(risk.dhs_risk?.score_10), align: "right" },
        { key: "dhs-priority", header: "우선순위", render: (risk) => <DhsPriorityBadge priority={risk.dhs_risk?.priority} /> },
        { key: "factor-a", header: "A 계수", render: (risk) => formatFactor(risk.factors.a), align: "right" },
        { key: "factor-d", header: "D 계수", render: (risk) => formatFactor(risk.factors.d), align: "right" },
        { key: "factor-e", header: "E 계수", render: (risk) => formatFactor(risk.factors.e), align: "right" },
        { key: "factor-l", header: "L 계수", render: (risk) => formatFactor(risk.factors.l), align: "right" },
        { key: "factor-c", header: "C 계수", render: (risk) => formatFactor(risk.factors.c), align: "right" },
        { key: "computed", header: "계산 시각", render: (risk) => formatDateTime(risk.computed_at) }
      ]}
    />
  );
}

function formatFactor(value: number) {
  return value.toFixed(2);
}
