import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { RiskWeightsInput, Schema } from "../../api/types";
import { PageHeader } from "../../components/common/PageHeader";
import { ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Field, FieldHint, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { yesNoLabel } from "../../domain/displayLabels";
import { areRiskWeightsValid, updateRiskWeight } from "../../domain/riskWeights";
import { useUiStore } from "../../stores/uiStore";
import { RiskFormulaHelp, riskWeightLabel } from "../risk/RiskFormulaHelp";

type AlgorithmRiskRow = Schema<"AlgorithmRiskTable">["items"][number];

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
  const [weights, setWeights] = useState<RiskWeightsInput>({ wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 });
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
  const weightsReady = Boolean(riskWeights.data) && !riskWeights.isError && areRiskWeightsValid(weights);

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
            <CardTitle>위험 가중치</CardTitle>
          </CardHeader>
          <CardContent>
            {riskWeights.isLoading ? <LoadingState /> : null}
            {riskWeights.isError ? <ErrorState error={riskWeights.error} onRetry={() => void riskWeights.refetch()} /> : null}
            <RiskFormulaHelp />
            {!areRiskWeightsValid(weights) ? <div className="callout state-view--error" role="alert">가중치는 0.5부터 2.0 사이 숫자여야 합니다.</div> : null}
            <div className="form-grid">
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
