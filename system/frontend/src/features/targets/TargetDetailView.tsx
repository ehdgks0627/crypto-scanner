import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { PageHeader } from "../../components/common/PageHeader";
import { ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { isTerminalJobStatus } from "../../domain/jobStatus";
import { formatDateTime } from "../../lib/format";
import { useJobWatchStore } from "../../stores/jobWatchStore";
import { TargetForm, targetToFormValues } from "./TargetForms";

export function TargetDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const trackJob = useJobWatchStore((state) => state.trackJob);
  const [editing, setEditing] = useState(false);
  const [recomputeJobId, setRecomputeJobId] = useState<number | null>(null);
  const target = useQuery({
    queryKey: queryKeys.targets.detail(id),
    queryFn: () => services.targets.get(id)
  });
  const patchTarget = useMutation({
    mutationFn: (payload: Schema<"TargetPatch">) => services.targets.patch(id, payload),
    onSuccess: async (result) => {
      toast.success(result.recompute_job_id ? `저장했습니다. Recompute job #${result.recompute_job_id}` : "저장했습니다.");
      setEditing(false);
      setRecomputeJobId(result.recompute_job_id);
      if (result.recompute_job_id) {
        trackJob(result.recompute_job_id);
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.detail(id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.assets.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "저장 실패")
  });
  const recomputeJob = useQuery({
    queryKey: recomputeJobId ? queryKeys.jobs.detail(recomputeJobId) : ["jobs", "detail", "target-context-none"],
    queryFn: () => services.jobs.get(recomputeJobId!),
    enabled: Boolean(recomputeJobId),
    refetchInterval: (query) => (query.state.data?.status === "PENDING" || query.state.data?.status === "RUNNING" ? 3_000 : false)
  });

  useEffect(() => {
    if (recomputeJob.data?.status === "COMPLETED") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.migration.all });
      toast.success("Target context recompute 완료");
      setRecomputeJobId(null);
    }
    if (recomputeJob.data?.status && isTerminalJobStatus(recomputeJob.data.status) && recomputeJob.data.status !== "COMPLETED") {
      toast.error(recomputeJob.data.status === "CANCELLED" ? "Target context recompute 취소됨" : "Target context recompute 실패");
      setRecomputeJobId(null);
    }
  }, [queryClient, recomputeJob.data?.status]);

  if (target.isLoading) {
    return <LoadingState />;
  }
  if (target.isError || !target.data) {
    return <ErrorState error={target.error} onRetry={() => void target.refetch()} />;
  }

  return (
    <Section>
      <PageHeader
        title={target.data.host}
        description={`${target.data.transport}/${target.data.port} · ${target.data.protocol_hint}`}
        actions={
          <>
            <Button type="button" onClick={() => navigate(`/scans/new?target_id=${target.data.id}`)}>스캔 시작</Button>
            <Button type="button" variant="primary" onClick={() => setEditing((value) => !value)}>
              <Save size={15} />{editing ? "닫기" : "수정"}
            </Button>
          </>
        }
      />

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>타겟 수정</CardTitle>
          </CardHeader>
          <CardContent>
            <TargetForm
              initialValue={targetToFormValues(target.data)}
              mode="patch"
              submitLabel="저장"
              isSubmitting={patchTarget.isPending}
              onCancel={() => setEditing(false)}
              onSubmit={(payload) => patchTarget.mutate(payload as Schema<"TargetPatch">)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="content-grid">
        {recomputeJob.data ? <div className="callout is-wide" role="status" aria-live="polite">Recompute #{recomputeJob.data.id}: {recomputeJob.data.status}</div> : null}
        <Card>
          <CardHeader>
            <CardTitle>기본 정보</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>ID</dt><dd>#{target.data.id}</dd></div>
              <div><dt>IP</dt><dd>{target.data.ip ?? "-"}</dd></div>
              <div><dt>SNI</dt><dd>{target.data.sni ?? "-"}</dd></div>
              <div><dt>Agent</dt><dd><Badge tone={target.data.agent_enabled ? "green" : "neutral"}>{target.data.agent_enabled ? "enabled" : "disabled"}</Badge></dd></div>
              <div><dt>Created</dt><dd>{formatDateTime(target.data.created_at)}</dd></div>
              <div><dt>Updated</dt><dd>{formatDateTime(target.data.updated_at)}</dd></div>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>운영 컨텍스트</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="detail-list">
              <div><dt>Sensitivity</dt><dd>{target.data.context.sensitivity ?? "-"}</dd></div>
              <div><dt>Lifespan</dt><dd>{target.data.context.lifespan_years ?? "-"}</dd></div>
              <div><dt>Criticality</dt><dd>{target.data.context.criticality ?? "-"}</dd></div>
              <div><dt>Exposure</dt><dd>{target.data.context.exposure ?? "-"}</dd></div>
              <div><dt>Service Role</dt><dd>{target.data.context.service_role ?? "-"}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
