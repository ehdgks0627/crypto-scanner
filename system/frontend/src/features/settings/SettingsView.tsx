import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { RiskWeightsInput, Schema } from "../../api/types";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Field, FieldHint, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { yesNoLabel } from "../../domain/displayLabels";
import { areRiskWeightsValid, updateRiskWeight } from "../../domain/riskWeights";
import { formatNumber } from "../../lib/format";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";
import { useUiStore } from "../../stores/uiStore";
import { RiskFormulaHelp, riskWeightLabel } from "../risk/RiskFormulaHelp";

type AlgorithmRiskRow = Schema<"AlgorithmRiskTable">["items"][number];
type CleanupAction = "snapshots" | "scanTargets";

const factorFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 4
});

function formatFactorA(value: number) {
  return factorFormatter.format(value);
}

function formatNotes(notes: AlgorithmRiskRow["notes"]) {
  return notes?.trim() ? notes : "-";
}

export function SettingsView() {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useUiStore();
  const clearSelectedSnapshotId = useSnapshotSelectionStore((state) => state.clearSelectedSnapshotId);
  const [weights, setWeights] = useState<RiskWeightsInput>({ wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 });
  const [cleanupAction, setCleanupAction] = useState<CleanupAction | null>(null);
  const riskWeights = useQuery({ queryKey: queryKeys.risk.weights, queryFn: () => services.risk.weights() });
  const algorithmRiskTable = useQuery({ queryKey: queryKeys.meta.algorithmRiskTable, queryFn: () => services.meta.algorithmRiskTable() });
  const algorithmRiskRows = algorithmRiskTable.data?.items ?? [];
  const saveWeights = useMutation({
    mutationFn: () => services.risk.putWeights(weights),
    onSuccess: async () => {
      toast.success("기본 가중치를 저장했습니다.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.risk.weights });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "저장 실패")
  });
  const cleanup = useMutation({
    mutationFn: (action: CleanupAction) => (action === "snapshots" ? services.settings.deleteSnapshots() : services.settings.deleteScanTargets()),
    onSuccess: async (result, action) => {
      if (action === "snapshots") {
        clearSelectedSnapshotId();
      }
      toast.success(cleanupSuccessMessage(action, result.deleted));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.targets.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.risk.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.migration.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.performance.all })
      ]);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "삭제 실패"),
    onSettled: () => setCleanupAction(null)
  });
  const weightsReady = Boolean(riskWeights.data) && !riskWeights.isError && areRiskWeightsValid(weights);
  const cleanupDialog = cleanupAction ? cleanupDialogContent(cleanupAction) : null;

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

  return (
    <Section>
      <PageHeader title="설정" description="화면 테마, 부트스트랩 토큰, 위험평가 기본 가중치를 관리합니다." />
      {cleanupDialog ? (
        <ConfirmDialog
          open
          title={cleanupDialog.title}
          description={cleanupDialog.description}
          confirmLabel="삭제 실행"
          pending={cleanup.isPending}
          onCancel={() => setCleanupAction(null)}
          onConfirm={() => cleanup.mutate(cleanupAction!)}
        />
      ) : null}
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>화면</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="form-grid">
              <Field>
                <FieldLabel>테마</FieldLabel>
                <Select value={theme} onChange={(event) => setTheme(event.target.value as "light" | "dark")}>
                  <option value="light">라이트</option>
                  <option value="dark">다크</option>
                </Select>
              </Field>
              <Field>
                <FieldLabel>부트스트랩 토큰</FieldLabel>
                <Input value="****" readOnly aria-label="부트스트랩 토큰 마스킹" />
                <FieldHint>변경은 docker env에서만 수행합니다.</FieldHint>
              </Field>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>데이터 정리</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="section-stack">
              <div className="callout">
                <strong>스냅샷/식별 자산</strong>
                <p className="muted">CBOM 스냅샷, 식별 자산, 위험 점수, 가용성 검사, 스캔 작업 이력을 삭제합니다.</p>
                <Button type="button" variant="danger" disabled={cleanup.isPending} onClick={() => setCleanupAction("snapshots")}>
                  <Trash2 size={15} />스냅샷/식별 자산 삭제
                </Button>
              </div>
              <div className="callout">
                <strong>스캔 대상</strong>
                <p className="muted">자동 등록 또는 직접 등록된 스캔 대상을 삭제합니다. Agent 등록 정보는 유지됩니다.</p>
                <Button type="button" variant="danger" disabled={cleanup.isPending} onClick={() => setCleanupAction("scanTargets")}>
                  <Trash2 size={15} />스캔 대상 삭제
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>위험 가중치</CardTitle>
          </CardHeader>
          <CardContent>
            {riskWeights.isLoading ? <LoadingState /> : null}
            {riskWeights.isError ? <ErrorState error={riskWeights.error} onRetry={() => void riskWeights.refetch()} /> : null}
            <RiskFormulaHelp />
            {!areRiskWeightsValid(weights) ? <div className="callout state-view--error" role="alert">가중치는 0.5부터 2.0 사이 숫자여야 합니다.</div> : null}
            <div className="form-grid risk-weight-grid" role="group" aria-label="위험 가중치 입력">
              {(Object.keys(weights) as Array<keyof RiskWeightsInput>).map((key) => (
                <Field key={key}>
                  <FieldLabel>{riskWeightLabel(key)}</FieldLabel>
                  <Input
                    type="number"
                    min="0.5"
                    max="2"
                    step="0.1"
                    value={Number.isNaN(weights[key]) ? "" : weights[key]}
                    onChange={(event) => setWeights((current) => updateRiskWeight(current, key, event.target.value))}
                  />
                </Field>
              ))}
            </div>
            <div className="form-actions">
              <Button type="button" variant="primary" disabled={!weightsReady || saveWeights.isPending} onClick={() => saveWeights.mutate()}>
                <Save size={15} />저장
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>알고리즘 위험도 테이블</CardTitle>
        </CardHeader>
        <CardContent>
          {algorithmRiskTable.isLoading ? <LoadingState /> : null}
          {algorithmRiskTable.isError ? <ErrorState error={algorithmRiskTable.error} onRetry={() => void algorithmRiskTable.refetch()} /> : null}
          {!algorithmRiskTable.isLoading && !algorithmRiskTable.isError ? (
            <DataTable
              items={algorithmRiskRows}
              getRowKey={(row, index) => `${row.algorithm}-${index}`}
              empty="설정된 규칙이 없습니다"
              columns={[
                { key: "algorithm", header: "알고리즘", render: (row) => row.algorithm },
                { key: "factor_a", header: "A 계수", align: "right", render: (row) => formatFactorA(row.factor_a) },
                {
                  key: "quantum_vulnerable",
                  header: "양자 취약 여부",
                  align: "center",
                  render: (row) => <Badge tone={row.quantum_vulnerable ? "red" : "green"}>{yesNoLabel(row.quantum_vulnerable)}</Badge>
                },
                { key: "notes", header: "비고", render: (row) => formatNotes(row.notes) }
              ]}
            />
          ) : null}
        </CardContent>
      </Card>
    </Section>
  );
}

function cleanupDialogContent(action: CleanupAction) {
  if (action === "snapshots") {
    return {
      title: "스냅샷/식별 자산 삭제",
      description: "모든 CBOM 스냅샷, 식별 자산, 위험 점수, 가용성 검사, 스캔 작업 이력을 삭제합니다. Agent와 스캔 대상은 유지됩니다."
    };
  }
  return {
    title: "스캔 대상 삭제",
    description: "자동 등록 또는 직접 등록된 모든 스캔 대상을 삭제합니다. 스냅샷과 Agent 등록 정보는 삭제하지 않습니다."
  };
}

function cleanupSuccessMessage(action: CleanupAction, deleted: Record<string, number>) {
  if (action === "snapshots") {
    return `스냅샷 ${formatNumber(deleted.snapshots)}개, 식별 자산 ${formatNumber(deleted.assets)}개를 삭제했습니다.`;
  }
  return `스캔 대상 ${formatNumber(deleted.scan_targets)}개를 삭제했습니다.`;
}
