import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { RiskWeightsInput } from "../../api/types";
import { JsonPreview } from "../../components/common/JsonPreview";
import { PageHeader } from "../../components/common/PageHeader";
import { ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { areRiskWeightsValid, updateRiskWeight } from "../../domain/riskWeights";
import { useUiStore } from "../../stores/uiStore";

export function SettingsView() {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useUiStore();
  const [weights, setWeights] = useState<RiskWeightsInput>({ wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 });
  const riskWeights = useQuery({ queryKey: queryKeys.risk.weights, queryFn: () => services.risk.weights() });
  const algorithmRiskTable = useQuery({ queryKey: queryKeys.meta.algorithmRiskTable, queryFn: () => services.meta.algorithmRiskTable() });
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
      <PageHeader title="설정" description="UI 테마, Bootstrap token, Risk 기본 가중치를 관리합니다." />
      <div className="content-grid">
        <Card>
          <CardHeader>
            <CardTitle>UI</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="form-grid">
              <Field>
                <FieldLabel>Theme</FieldLabel>
                <Select value={theme} onChange={(event) => setTheme(event.target.value as "light" | "dark")}>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </Select>
              </Field>
              <Field>
                <FieldLabel>Bootstrap Token</FieldLabel>
                <Input value="****" readOnly aria-label="Bootstrap Token masked" />
                <span className="muted">변경은 docker env에서만 수행합니다.</span>
              </Field>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Risk Weights</CardTitle>
          </CardHeader>
          <CardContent>
            {riskWeights.isLoading ? <LoadingState /> : null}
            {riskWeights.isError ? <ErrorState error={riskWeights.error} onRetry={() => void riskWeights.refetch()} /> : null}
            {!areRiskWeightsValid(weights) ? <div className="callout state-view--error" role="alert">가중치는 0.5부터 2.0 사이 숫자여야 합니다.</div> : null}
            <div className="form-grid">
              {(Object.keys(weights) as Array<keyof RiskWeightsInput>).map((key) => (
                <Field key={key}>
                  <FieldLabel>{key}</FieldLabel>
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
          <CardTitle>Algorithm Risk Table</CardTitle>
        </CardHeader>
        <CardContent>
          {algorithmRiskTable.data ? <JsonPreview value={algorithmRiskTable.data} /> : <LoadingState />}
        </CardContent>
      </Card>
    </Section>
  );
}
