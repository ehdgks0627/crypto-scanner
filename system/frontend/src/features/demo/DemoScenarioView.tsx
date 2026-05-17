import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Download, FileJson, Gauge, ListChecks, Play, RotateCcw, ShieldCheck, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import type { DemoAsset, DemoHostLabel, DemoSession, DemoTarget } from "../../api/demoTypes";
import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import { JsonPreview } from "../../components/common/JsonPreview";
import { PageHeader } from "../../components/common/PageHeader";
import { ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { Progress } from "../../components/ui/progress";
import { DataTable } from "../../components/ui/table";
import { downloadJson, downloadText } from "../../lib/download";

type CbomMode = "standard" | "enriched";

const stepIcons = {
  targets: Target,
  agents: Bot,
  cbom: FileJson,
  risk: Gauge,
  migration: ListChecks,
  verification: ShieldCheck
} as const;

export function DemoScenarioView() {
  const queryClient = useQueryClient();
  const [cbomMode, setCbomMode] = useState<CbomMode>("enriched");
  const [selectedAssetId, setSelectedAssetId] = useState("srv-01:443/tls");
  const session = useQuery({
    queryKey: queryKeys.demo.session,
    queryFn: () => services.demo.session(),
    refetchInterval: 10_000
  });
  const events = useQuery({
    queryKey: queryKeys.demo.events,
    queryFn: () => services.demo.events(),
    refetchInterval: 5_000
  });
  const start = useMutation({
    mutationFn: () => services.demo.start(),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.demo.session, data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.demo.events });
      toast.success("시연을 처음 단계로 되돌렸습니다.");
    }
  });
  const next = useMutation({
    mutationFn: () => services.demo.next(),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.demo.session, data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.demo.events });
      toast.success(`${data.steps[data.current_step].title} 단계가 준비되었습니다.`);
    }
  });

  const data = session.data;
  const selectedAsset = useMemo(
    () => data?.assets.find((asset) => asset.id === selectedAssetId) ?? data?.assets[0] ?? null,
    [data?.assets, selectedAssetId]
  );
  const currentStep = data?.steps[data.current_step];
  const canAdvance = Boolean(
    data &&
    !data.last_error &&
    data.current_step < data.steps.length - 1 &&
    (currentStep?.status === "completed" || currentStep?.status === "ready")
  );

  if (session.isLoading) {
    return <LoadingState />;
  }

  if (session.isError || !data) {
    return <ErrorState error={session.error} onRetry={() => void session.refetch()} />;
  }

  return (
    <Section>
      <PageHeader
        title="최종 시연"
        eyebrow="NIST SP 1800-38 절차"
        description="찾기, 정리하기, 계획하기, 확인하기 흐름을 한 화면에서 순서대로 실행합니다."
        actions={
          <div className="inline-actions">
            <Button type="button" onClick={() => start.mutate()} disabled={start.isPending}>
              <RotateCcw size={15} />처음으로
            </Button>
            <Button type="button" variant="primary" onClick={() => next.mutate()} disabled={next.isPending || !canAdvance}>
              <Play size={15} />다음 단계
            </Button>
          </div>
        }
      />

      {data.last_error && (
        <Card className="demo-error-card">
          <CardContent>
            <strong>단계 실행 실패</strong>
            <span>{data.last_error}</span>
            {data.can_retry && (
              <Button type="button" size="sm" onClick={() => next.mutate()} disabled={next.isPending}>
                재시도
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <DemoStepper session={data} />

      <div className="demo-grid">
        <div className="demo-main">
          {data.current_step_id === "targets" && <StepTargets targets={data.targets} labels={data.host_labels} />}
          {data.current_step_id === "agents" && <StepAgents session={data} />}
          {data.current_step_id === "cbom" && (
            <StepCbom
              assets={data.assets}
              mode={cbomMode}
              selectedAsset={selectedAsset}
              onModeChange={setCbomMode}
              onSelectAsset={setSelectedAssetId}
            />
          )}
          {data.current_step_id === "risk" && <StepRisk session={data} selectedAsset={selectedAsset} onSelectAsset={setSelectedAssetId} />}
          {data.current_step_id === "migration" && <StepMigration session={data} />}
          {data.current_step_id === "verification" && <StepVerification session={data} />}
        </div>

        <aside className="demo-side">
          <Card>
            <CardHeader>
              <CardTitle>진행 로그</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="demo-event-list">
                {(events.data?.items ?? []).map((event, index) => (
                  <li key={`${event.step}-${index}`}>
                    <CheckCircle2 size={14} />
                    <span>{event.message}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>고정 시연 수치</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="demo-fact-grid">
                <DemoFact label="자산" value="47" />
                <DemoFact label="Discovery" value="28" />
                <DemoFact label="Host" value="24" />
                <DemoFact label="Overlap" value="5" />
                <DemoFact label="P1/P2/P3" value="12/8/27" />
                <DemoFact label="추천" value="20" />
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </Section>
  );
}

function DemoStepper({ session }: { session: DemoSession }) {
  return (
    <div className="demo-stepper">
      {session.steps.map((step) => {
        const Icon = stepIcons[step.id];
        return (
          <div key={step.id} className={`demo-step demo-step--${step.status}`}>
            <span className="demo-step__icon"><Icon size={16} /></span>
            <div>
              <strong>{step.title}</strong>
              <span>{step.subtitle}</span>
              <small>{step.status === "locked" ? "대기" : `${step.progress}%`}</small>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StepTargets({ targets, labels }: { targets: DemoTarget[]; labels: DemoHostLabel[] }) {
  const demoAddTarget = () => toast.success("시연 대상 13개가 이미 준비되어 있습니다.");
  return (
    <div className="demo-two-col">
      <Card>
        <CardHeader><CardTitle>탐색 대상</CardTitle></CardHeader>
        <CardContent>
          <form className="demo-form-panel" onSubmit={(event) => { event.preventDefault(); demoAddTarget(); }}>
            <div className="demo-form-grid">
              <Field className="is-wide">
                <FieldLabel>IP / Domain / CIDR</FieldLabel>
                <Input defaultValue="10.0.0.0/24" aria-label="IP / Domain / CIDR" />
              </Field>
              <Field>
                <FieldLabel>서비스 힌트</FieldLabel>
                <Select defaultValue="auto" aria-label="service hint">
                  <option value="auto">자동 감지</option>
                  <option value="tls">TLS</option>
                  <option value="ssh">SSH</option>
                  <option value="starttls">STARTTLS</option>
                  <option value="ike">IKE</option>
                </Select>
              </Field>
              <Field>
                <FieldLabel>탐색 방식</FieldLabel>
                <Select defaultValue="discovery" aria-label="target role">
                  <option value="discovery">Discovery Agent</option>
                  <option value="host">Host Agent</option>
                </Select>
              </Field>
            </div>
            <div className="form-actions">
              <Button type="submit" size="sm">대상 추가</Button>
            </div>
          </form>
          <DataTable
            items={targets}
            getRowKey={(item) => item.id}
            columns={[
              { key: "value", header: "대상", render: (item) => item.value },
              { key: "kind", header: "유형", render: (item) => <Badge>{item.kind}</Badge> },
              { key: "service", header: "서비스", render: (item) => item.service }
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>호스트 라벨</CardTitle></CardHeader>
        <CardContent>
          <form className="demo-form-panel">
            <div className="demo-form-grid">
              <Field>
                <FieldLabel>role</FieldLabel>
                <Select defaultValue="edge-proxy" aria-label="role">
                  <option value="edge-proxy">edge-proxy</option>
                  <option value="auth">auth</option>
                  <option value="db">db</option>
                  <option value="monitoring">monitoring</option>
                </Select>
              </Field>
              <Field>
                <FieldLabel>retention</FieldLabel>
                <Select defaultValue="7y" aria-label="retention">
                  <option value="1y">1y</option>
                  <option value="3y">3y</option>
                  <option value="5y">5y</option>
                  <option value="7y">7y</option>
                  <option value="10y+">10y+</option>
                </Select>
              </Field>
              <div className="ui-field is-wide">
                <FieldLabel>data_classes</FieldLabel>
                <div className="demo-check-list">
                  {["PII", "payment", "internal-only", "credential"].map((item) => (
                    <label key={item}>
                      <Checkbox defaultChecked={item === "PII" || item === "payment"} />
                      <span>{item}</span>
                    </label>
                  ))}
                </div>
              </div>
              <Field className="is-wide">
                <FieldLabel>partners</FieldLabel>
                <Input defaultValue="PG-A" aria-label="partners" />
              </Field>
            </div>
          </form>
          <div className="demo-label-list">
            {labels.map((label) => (
              <div key={label.host} className="demo-label-card">
                <div>
                  <strong>{label.host}</strong>
                  <span>{label.description}</span>
                </div>
                <dl>
                  <div><dt>role</dt><dd>{label.role}</dd></div>
                  <div><dt>data</dt><dd>{label.data_classes.join(", ")}</dd></div>
                  <div><dt>partners</dt><dd>{label.partners.join(", ") || "-"}</dd></div>
                  <div><dt>retention</dt><dd>{label.retention}</dd></div>
                </dl>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StepAgents({ session }: { session: DemoSession }) {
  return (
    <div className="demo-stack">
      <Card>
        <CardHeader><CardTitle>Agent 실행 진행</CardTitle></CardHeader>
        <CardContent>
          <div className="demo-progress-row">
            <strong>{session.agent_run.progress}%</strong>
            <span>{session.agent_run.status === "completed" ? "47 / 47 자산 정리 완료" : "0 / 47 자산 정리 대기"}</span>
          </div>
          <Progress value={session.agent_run.progress} />
        </CardContent>
      </Card>
      <div className="content-grid content-grid--4">
        <DemoMetric label="총 자산" value={session.agent_run.total_assets} />
        <DemoMetric label="Discovery Agent" value={session.agent_run.discovery_assets} />
        <DemoMetric label="Host Agent" value={session.agent_run.host_assets} />
        <DemoMetric label="잠든 키" value={session.agent_run.dormant_keys} tone="yellow" />
      </div>
      <DemoMetric label="중복 제거" value={`${session.agent_run.overlap_assets}개`} />
      <div className="demo-two-col">
        <AgentLog title="Discovery Agent" logs={session.agent_run.logs.discovery} />
        <AgentLog title="Host Agent" logs={session.agent_run.logs.host} />
      </div>
      <Card>
        <CardHeader><CardTitle>알고리즘 분포</CardTitle></CardHeader>
        <CardContent>
          <div className="demo-bar-list">
            {session.agent_run.algorithm_distribution.map((item) => (
              <div key={item.label} className="demo-bar-row">
                <span>{item.label}</span>
                <div><i style={{ width: `${(item.count / 14) * 100}%` }} /></div>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StepCbom({
  assets,
  mode,
  selectedAsset,
  onModeChange,
  onSelectAsset
}: {
  assets: DemoAsset[];
  mode: CbomMode;
  selectedAsset: DemoAsset | null;
  onModeChange: (mode: CbomMode) => void;
  onSelectAsset: (assetId: string) => void;
}) {
  return (
    <div className="demo-two-col demo-two-col--wide-left">
      <Card>
        <CardHeader>
          <CardTitle>CBOM 자산 목록</CardTitle>
          <div className="inline-actions">
            <div className="demo-segmented">
              <button type="button" className={mode === "standard" ? "is-active" : undefined} onClick={() => onModeChange("standard")}>표준</button>
              <button type="button" className={mode === "enriched" ? "is-active" : undefined} onClick={() => onModeChange("enriched")}>확장</button>
            </div>
            <Button type="button" size="sm" onClick={() => downloadJson(`demo-cbom-${mode}.json`, assets.map((asset) => cbomJson(asset, mode)))}>
              <Download size={14} />Export
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <DataTable
            items={assets}
            getRowKey={(item) => item.id}
            onRowClick={(item) => onSelectAsset(item.id)}
            columns={[
              { key: "id", header: "ID", render: (item) => item.id },
              { key: "algorithm", header: "알고리즘", render: (item) => item.algorithm },
              { key: "key_size", header: "키", render: (item) => item.key_size ? `${item.key_size} bit` : "-" },
              { key: "expires", header: "만료일", render: (item) => item.expires },
              { key: "domain", header: "도메인", render: (item) => item.domain },
              ...(mode === "enriched"
                ? [
                    { key: "role", header: "역할", render: (item: DemoAsset) => item.role },
                    { key: "neighbors", header: "연결 대상", render: (item: DemoAsset) => item.neighbors.join(", ") || "-" },
                    { key: "data", header: "취급 정보", render: (item: DemoAsset) => item.data_tags.join(", ") },
                    { key: "retention", header: "보존", render: (item: DemoAsset) => item.retention }
                  ]
                : [])
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>선택 자산 JSON</CardTitle></CardHeader>
        <CardContent><JsonPreview value={selectedAsset ? cbomJson(selectedAsset, mode) : null} /></CardContent>
      </Card>
    </div>
  );
}

function StepRisk({
  session,
  selectedAsset,
  onSelectAsset
}: {
  session: DemoSession;
  selectedAsset: DemoAsset | null;
  onSelectAsset: (id: string) => void;
}) {
  const progress = session.risk.status === "completed" ? 100 : 0;
  return (
    <div className="demo-stack">
      <Card>
        <CardHeader><CardTitle>DHS 6기준 평가 진행</CardTitle></CardHeader>
        <CardContent>
          <div className="demo-progress-row">
            <strong>{progress}%</strong>
            <span>{session.risk.status === "completed" ? "47 / 47 자산 평가 완료" : "0 / 47 자산 평가 대기"}</span>
          </div>
          <Progress value={progress} />
        </CardContent>
      </Card>
      <div className="content-grid content-grid--3">
        <DemoMetric label="P1" value={session.risk.summary.P1} tone="red" />
        <DemoMetric label="P2" value={session.risk.summary.P2} tone="yellow" />
        <DemoMetric label="P3" value={session.risk.summary.P3} />
      </div>
      <div className="demo-two-col demo-two-col--wide-left">
        <Card>
          <CardHeader><CardTitle>평가 결과</CardTitle></CardHeader>
          <CardContent>
            <DataTable
              items={session.assets}
              getRowKey={(item) => item.id}
              onRowClick={(item) => onSelectAsset(item.id)}
              columns={[
                { key: "id", header: "자산", render: (item) => item.id },
                {
                  key: "status",
                  header: "상태",
                  render: () => session.risk.status === "completed" ? <Badge tone="green">완료</Badge> : <span className="demo-inline-spinner">평가 중</span>
                },
                { key: "score", header: "점수", align: "right", render: (item) => item.risk_score.toFixed(1) },
                { key: "priority", header: "우선순위", render: (item) => <PriorityBadge priority={item.priority} /> },
                { key: "data", header: "컨텍스트", render: (item) => item.data_tags.join(", ") }
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>선택 자산 DHS 응답</CardTitle></CardHeader>
          <CardContent><JsonPreview value={riskJson(selectedAsset, session)} /></CardContent>
        </Card>
      </div>
    </div>
  );
}

function StepMigration({ session }: { session: DemoSession }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>추천 대상 {session.migration.recommendation_count}개</CardTitle>
        <Button type="button" size="sm" onClick={() => downloadText("demo-migration-plan.md", migrationReport(session), "text/markdown;charset=utf-8")}>
          <Download size={14} />Export
        </Button>
      </CardHeader>
      <CardContent>
        <p className="demo-note">자동 변경이 아니라 전환 계획 추천입니다.</p>
        <DataTable
          items={session.migration.items}
          getRowKey={(item) => item.asset_id}
          columns={[
            { key: "asset", header: "자산", render: (item) => item.asset_id },
            { key: "current", header: "현재", render: (item) => item.current_algorithm },
            { key: "next", header: "추천", render: (item) => item.recommended_algorithm },
            { key: "priority", header: "우선순위", render: (item) => <PriorityBadge priority={item.priority} /> },
            { key: "reason", header: "사유", render: (item) => item.reason }
          ]}
        />
      </CardContent>
    </Card>
  );
}

function StepVerification({ session }: { session: DemoSession }) {
  const verification = session.verification;
  return (
    <div className="demo-stack">
      <div className="content-grid content-grid--4">
        <DemoMetric label="종합" value={verification.overall_status ?? "-"} tone="green" />
        <DemoMetric label="핸드셰이크" value={`${verification.handshake_success_rate}%`} tone="green" />
        <DemoMetric label="지연" value={`${verification.latency_before_ms}->${verification.latency_after_ms}ms`} />
        <DemoMetric label="처리량" value={`${verification.throughput_before_rps}->${verification.throughput_after_rps}`} />
        <DemoMetric label="실패" value={`${verification.failure_count ?? 0}건`} tone="green" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>4차원 가용성 검증</CardTitle>
          <Button type="button" size="sm" onClick={() => downloadJson("demo-availability-report.json", verification)}>
            <Download size={14} />Export
          </Button>
        </CardHeader>
        <CardContent>
          <div className="demo-verification-grid">
            {(verification.checks ?? []).map((check) => (
              <div key={check.name} className="demo-check-card">
                <Badge tone="green">{check.status}</Badge>
                <strong>{check.name}</strong>
                <span>{check.value}</span>
              </div>
            ))}
          </div>
          <div className="demo-compare-grid">
            <CompareBar label="호환성" before={verification.compatibility_before ?? 0} after={verification.compatibility_after ?? 0} unit="%" />
            <CompareBar label="CBOM 변경" before={0} after={verification.cbom_changes ?? 0} unit="개" max={12} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function AgentLog({ title, logs }: { title: string; logs: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <ol className="demo-log-list">
          {logs.map((log, index) => (
            <li key={log}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {log}
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function DemoMetric({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "green" | "yellow" | "red" }) {
  return (
    <Card className={`demo-metric demo-metric--${tone}`}>
      <CardContent>
        <span>{label}</span>
        <strong>{value}</strong>
      </CardContent>
    </Card>
  );
}

function DemoFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PriorityBadge({ priority }: { priority: "P1" | "P2" | "P3" }) {
  const tone = priority === "P1" ? "red" : priority === "P2" ? "yellow" : "neutral";
  return <Badge tone={tone}>{priority}</Badge>;
}

function CompareBar({ label, before, after, unit, max = 100 }: { label: string; before: number; after: number; unit: string; max?: number }) {
  return (
    <div className="demo-compare">
      <div>
        <strong>{label}</strong>
        <span>{before}{unit} -&gt; {after}{unit}</span>
      </div>
      <Progress value={(after / max) * 100} />
    </div>
  );
}

function cbomJson(asset: DemoAsset, mode: CbomMode) {
  const base = {
    "bom-ref": asset.id,
    name: asset.name,
    type: "cryptographic-asset",
    asset_type: asset.asset_type,
    algorithm: asset.algorithm_group,
    key_size: asset.key_size,
    expires: asset.expires,
    san: [asset.domain],
    fingerprint: `sha256:${asset.id.replace(/[^a-z0-9]/gi, "").slice(0, 16).padEnd(16, "0")}`
  };
  if (mode === "standard") {
    return base;
  }
  return {
    ...base,
    host_role: asset.role,
    neighbors: asset.neighbors,
    config_hints: asset.host === "srv-01" ? ["proxy_pass https://payments-api"] : [],
    data_tags: asset.data_tags,
    retention_policy: asset.retention,
    discovered_by: asset.discovered_by
  };
}

function riskJson(asset: DemoAsset | null, session: DemoSession) {
  if (!asset) {
    return null;
  }
  if (asset.id === session.risk.example?.asset_id) {
    return session.risk.example;
  }
  return {
    asset_id: asset.id,
    score: asset.risk_score,
    priority: asset.priority,
    criteria: {
      value: { level: asset.priority === "P1" ? "HIGH" : "MED", reason: `${asset.role} 역할 자산` },
      data: { level: asset.data_tags.length > 0 ? "HIGH" : "LOW", reason: asset.data_tags.join(", ") || "민감 정보 태그 없음" },
      scope: { level: asset.neighbors.length > 0 ? "MED" : "LOW", reason: asset.neighbors.join(", ") || "연결 대상 없음" },
      sharing: { level: "MED", reason: "발표용 deterministic fixture" },
      critical: { level: asset.quantum_vulnerable ? "HIGH" : "LOW", reason: asset.algorithm },
      lifetime: { level: asset.retention === "10y+" || asset.retention === "7y" ? "HIGH" : "MED", reason: asset.retention }
    }
  };
}

function migrationReport(session: DemoSession) {
  const lines = [
    "# PQC 매핑 추천",
    "",
    `- 추천 대상: ${session.migration.recommendation_count}개`,
    "- 범위: P1/P2 자산",
    "- 주의: 이 결과는 자동 변경이 아니라 전환 계획 추천입니다.",
    ""
  ];
  session.migration.items.forEach((item) => {
    lines.push(`## ${item.asset_id}`);
    lines.push(`- 현재 알고리즘: ${item.current_algorithm}`);
    lines.push(`- 추천 알고리즘: ${item.recommended_algorithm}`);
    lines.push(`- 우선순위: ${item.priority}`);
    lines.push(`- 사유: ${item.reason}`);
    lines.push("");
  });
  return lines.join("\n");
}
