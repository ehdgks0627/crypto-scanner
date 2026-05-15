import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { AssetType, Schema } from "../../api/types";
import { RiskTierBadge } from "../../components/common/Badges";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { MigrationReportBuilder } from "../../domain/migrationReport";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { agilityLevelLabel, assetTypeLabel, migrationPurposeLabel, riskTierLabel } from "../../domain/displayLabels";
import { parseRiskTierParam, riskTierOptions } from "../../domain/filterOptions";
import { downloadText } from "../../lib/download";
import { formatNumber, formatScore } from "../../lib/format";

type MigrationRow = Schema<"MigrationPlanItem">;

const assetTypeOptions: AssetType[] = ["algorithm", "certificate", "key", "key_agreement", "protocol", "keystore", "device", "service", "data"];

export function MigrationPlanView({ snapshotId }: { snapshotId: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tierParam = searchParams.get("tier") ?? "CRITICAL";
  const assetTypeParam = searchParams.get("asset_type") ?? "";
  const minScore = searchParams.get("min_score") ?? "70";
  const tier = parseRiskTierParam(tierParam);
  const assetType = assetTypeOptions.includes(assetTypeParam as AssetType) ? (assetTypeParam as AssetType) : "";
  const parsedMinScore = minScore === "" ? undefined : Number(minScore);
  const minScoreValid = parsedMinScore === undefined || (Number.isInteger(parsedMinScore) && parsedMinScore >= 0 && parsedMinScore <= 100);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const filters = useMemo(
    () => ({
      min_score: minScoreValid ? parsedMinScore : undefined,
      tier: tier ? [tier] : undefined,
      asset_type: assetType ? [assetType] : undefined
    }),
    [assetType, minScoreValid, parsedMinScore, tier]
  );
  const plan = useQuery({
    queryKey: queryKeys.migration.plan(snapshotId, filters),
    queryFn: () => services.migration.plan(snapshotId, filters),
    enabled: minScoreValid
  });
  const activeSelectedIds = useMemo(() => (minScoreValid ? selectedIds : []), [minScoreValid, selectedIds]);
  const normalizedSelectedIds = useMemo(() => [...new Set(activeSelectedIds)].sort((a, b) => a - b), [activeSelectedIds]);
  const reportSelectionAvailable = minScoreValid && normalizedSelectedIds.length > 0;
  const impact = useQuery({
    queryKey: queryKeys.migration.impact(snapshotId, normalizedSelectedIds),
    queryFn: () => services.migration.impact(snapshotId, normalizedSelectedIds),
    enabled: reportSelectionAvailable
  });

  const rows = minScoreValid ? plan.data?.items ?? [] : [];
  const selectedItems = useMemo(() => rows.filter((row) => activeSelectedIds.includes(row.asset_id)), [activeSelectedIds, rows]);
  const selectedVisibleRows = rows.filter((row) => activeSelectedIds.includes(row.asset_id));
  const allVisibleSelected = rows.length > 0 && selectedVisibleRows.length === rows.length;

  useEffect(() => {
    if (!minScoreValid || !plan.data) {
      return;
    }
    const rowIds = new Set(rows.map((row) => row.asset_id));
    setSelectedIds((current) => {
      const next = current.filter((id) => rowIds.has(id));
      return next.length === current.length ? current : next;
    });
  }, [minScoreValid, plan.data, rows]);

  function toggleItem(item: MigrationRow, checked: boolean) {
    setSelectedIds((current) => (checked ? [...current.filter((id) => id !== item.asset_id), item.asset_id] : current.filter((id) => id !== item.asset_id)));
  }

  function toggleVisibleRows(checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...current.filter((id) => !rows.some((row) => row.asset_id === id)), ...rows.map((row) => row.asset_id)] : current.filter((id) => !rows.some((row) => row.asset_id === id))
    );
  }

  function downloadReport() {
    const report = new MigrationReportBuilder(snapshotId, selectedItems, impact.data).buildMarkdown();
    downloadText(`snapshot-${snapshotId}-migration-report.md`, report, "text/markdown;charset=utf-8");
  }

  function setFilter(name: "tier" | "asset_type" | "min_score", value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(name, value);
    } else {
      next.delete(name);
    }
    setSearchParams(next);
  }

  return (
    <Section>
      <PageHeader
        title={`스냅샷 #${snapshotId} Review Targets`}
        description="위험 자산의 PQC 전환 후보와 영향도를 검토합니다."
        actions={
          <Button type="button" disabled={!reportSelectionAvailable || impact.isFetching} onClick={downloadReport}>
            <Download size={15} />보고서 다운로드
          </Button>
        }
      />
      <div className="callout" role="note">
        현재 화면은 전환 권고 검토와 보고서 생성 전용입니다. 인증서 재발급, 키 교체, 서비스 설정 변경은 수행하지 않습니다.
      </div>
      <div className="split-pane">
        <Card>
          <CardHeader>
            <CardTitle>전환 대상 계획</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="toolbar">
              <div className="toolbar__filters">
                <Select aria-label="마이그레이션 위험도 필터" value={tier} onChange={(event) => setFilter("tier", event.target.value)}>
                  <option value="">전체 등급</option>
                  {riskTierOptions.map((item) => (
                    <option key={item} value={item}>{riskTierLabel(item)}</option>
                  ))}
                </Select>
                <Select aria-label="마이그레이션 자산 타입 필터" value={assetType} onChange={(event) => setFilter("asset_type", event.target.value)}>
                  <option value="">전체 자산 타입</option>
                  {assetTypeOptions.map((item) => (
                    <option key={item} value={item}>{assetTypeLabel(item)}</option>
                  ))}
                </Select>
                <Field className="field-inline">
                  <FieldLabel>최소 점수</FieldLabel>
                  <Input type="number" min="0" max="100" value={minScore} onChange={(event) => setFilter("min_score", event.target.value)} />
                </Field>
              </div>
              <span className="inline-actions">
                <Checkbox
                  aria-label="현재 표시된 migration 항목 전체 선택"
                  checked={allVisibleSelected}
                  disabled={rows.length === 0}
                  onChange={(event) => toggleVisibleRows(event.target.checked)}
                />
                <span className="muted">표시 {rows.length} · 선택 {selectedItems.length}</span>
              </span>
            </div>
            {!minScoreValid ? <div className="callout state-view--error" role="alert">최소 점수는 0부터 100 사이의 정수여야 합니다.</div> : null}
            {minScoreValid && plan.isLoading ? <LoadingState /> : null}
            {minScoreValid && plan.isError ? <ErrorState error={plan.error} onRetry={() => void plan.refetch()} /> : null}
            {minScoreValid && plan.data ? (
              <DataTable
                items={rows}
                getRowKey={(item, index) => item.asset_id ?? item.current?.algorithm ?? index}
                empty={<EmptyState title="마이그레이션 항목이 없습니다" />}
                columns={[
                  {
                    key: "select",
                    header: "",
                    render: (item) =>
                      <Checkbox
                        checked={activeSelectedIds.includes(item.asset_id)}
                        onChange={(event) => toggleItem(item, event.target.checked)}
                        aria-label={`${item.asset_name} 선택`}
                      />
                  },
                  { key: "asset", header: "자산", render: (item) => item.asset_name ?? item.current?.algorithm ?? "-" },
                  { key: "purpose", header: "용도", render: (item) => migrationPurposeLabel(item.asset_purpose) },
                  { key: "current", header: "현재 알고리즘", render: (item) => item.current.algorithm ?? "-" },
                  { key: "strategy", header: "전략", render: (item) => item.recommendation.strategy },
                  { key: "phase", header: "단계", render: (item) => item.recommendation.phase },
                  { key: "target", header: "목표 알고리즘", render: (item) => item.recommendation.target_algorithm },
                  { key: "agility", header: "민첩성", render: (item) => <AgilityBadge agility={item.agility} /> },
                  { key: "score", header: "점수", render: (item) => formatScore(item.risk_score) },
                  { key: "tier", header: "등급", render: (item) => <RiskTierBadge tier={item.tier} /> }
                ]}
              />
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>영향도</CardTitle>
          </CardHeader>
          <CardContent>
            {!reportSelectionAvailable ? <EmptyState title="자산을 선택하세요" description="선택한 자산 기준으로 예상 작업량을 계산합니다." /> : null}
            {reportSelectionAvailable && impact.isFetching ? <LoadingState /> : null}
            {reportSelectionAvailable && impact.isError ? (
              <>
                <ErrorState error={impact.error} onRetry={() => void impact.refetch()} />
                <div className="callout">영향도 분석 없이 선택 항목 기준 보고서를 다운로드할 수 있습니다.</div>
              </>
            ) : null}
            {reportSelectionAvailable && impact.data ? <MigrationImpactSummary impact={impact.data} /> : null}
          </CardContent>
        </Card>
      </div>
      {reportSelectionAvailable ? (
        <Card>
          <CardHeader>
            <CardTitle>보고서 선택 항목</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              items={selectedItems}
              getRowKey={(item) => item.asset_id}
              columns={[
                { key: "asset", header: "자산", render: (item) => item.asset_name },
                { key: "purpose", header: "용도", render: (item) => migrationPurposeLabel(item.asset_purpose) },
                { key: "risk", header: "위험도", render: (item) => `${formatScore(item.risk_score)} / ${riskTierLabel(item.tier)}` },
                { key: "recommendation", header: "권고", render: (item) => `${item.recommendation.strategy} → ${item.recommendation.target_algorithm}` },
                { key: "agility", header: "민첩성", render: (item) => `${item.agility.score} / ${agilityLevelLabel(item.agility.level)}` },
                { key: "rationale", header: "근거", render: (item) => item.recommendation.rationale },
                {
                  key: "remove",
                  header: "",
                  align: "right",
                  render: (item) => (
                    <Button type="button" size="sm" variant="ghost" onClick={() => toggleItem(item, false)}>
                      제거
                    </Button>
                  )
                }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}
      {selectedItems.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>암호 민첩성 플레이북</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="migration-playbook-list">
              {selectedItems.map((item) => (
                <div key={item.asset_id} className="migration-playbook-item">
                  <div className="migration-playbook-item__header">
                    <strong>{item.asset_name}</strong>
                    <AgilityBadge agility={item.agility} />
                  </div>
                  <dl className="detail-list">
                    <div><dt>차단 요인</dt><dd>{item.agility.blockers.length ? item.agility.blockers.join(", ") : "-"}</dd></div>
                    <div><dt>롤백</dt><dd>{item.recommendation.rollback}</dd></div>
                    <div><dt>검증</dt><dd>{item.recommendation.validation.join(", ")}</dd></div>
                  </dl>
                  <ol className="migration-playbook-steps">
                    {item.playbook.map((step) => (
                      <li key={`${item.asset_id}-${step.order}`}>
                        <span className="mono">{step.kind}</span>
                        <strong>{step.title}</strong>
                        <span>{step.action}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </Section>
  );
}

function MigrationImpactSummary({ impact }: { impact: Schema<"MigrationImpact"> }) {
  const workloadRows = [
    { label: "선택 자산", value: formatNumber(impact.selected_count) },
    { label: "인증서 재발급", value: formatNumber(impact.cert_reissues) },
    { label: "설정 변경", value: formatNumber(impact.config_changes) },
    { label: "키 재생성", value: formatNumber(impact.key_regens) },
    { label: "예상 다운타임", value: `${formatNumber(impact.estimated_downtime_min)}분` }
  ];
  const endpointRows = buildImpactEndpointRows(impact);

  return (
    <div className="section-stack">
      <DataTable
        items={workloadRows}
        getRowKey={(item) => item.label}
        columns={[
          { key: "label", header: "작업 항목", render: (item) => item.label },
          { key: "value", header: "예상치", align: "right", render: (item) => item.value }
        ]}
      />
      <DataTable
        items={endpointRows}
        getRowKey={(item, index) => `${item.host}:${item.service}:${index}`}
        empty={<EmptyState title="영향 대상이 없습니다" />}
        columns={[
          { key: "host", header: "호스트", render: (item) => item.host },
          { key: "service", header: "서비스", render: (item) => item.service }
        ]}
      />
    </div>
  );
}

function buildImpactEndpointRows(impact: Schema<"MigrationImpact">) {
  const size = Math.max(impact.hosts.length, impact.services.length);
  return Array.from({ length: size }, (_, index) => ({
    host: impact.hosts[index] ?? "-",
    service: impact.services[index] ?? "-"
  }));
}

function AgilityBadge({ agility }: { agility: Schema<"MigrationAgility"> }) {
  const tone = agility.level === "HIGH" ? "green" : agility.level === "MEDIUM" ? "yellow" : "red";
  return <Badge tone={tone}>{agility.score} · {agilityLevelLabel(agility.level)}</Badge>;
}
