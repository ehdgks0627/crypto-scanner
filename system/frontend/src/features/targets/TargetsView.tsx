import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Dialog } from "../../components/ui/dialog";
import { Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { TargetModel } from "../../domain/models";
import { formatDateTime } from "../../lib/format";
import { TargetForm } from "./TargetForms";

export function TargetsView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Schema<"Target"> | null>(null);
  const [host, setHost] = useState("");
  const [protocol, setProtocol] = useState("");
  const filters = useMemo(() => ({ host: host || undefined, protocol_hint: protocol || undefined, limit: 100 }), [host, protocol]);
  const targets = useQuery({
    queryKey: queryKeys.targets.list(filters),
    queryFn: () => services.targets.list(filters)
  });
  const createTarget = useMutation({
    mutationFn: (payload: Schema<"TargetCreate">) => services.targets.create(payload),
    onSuccess: async (target) => {
      toast.success("타겟을 등록했습니다.");
      setCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.all });
      navigate(`/targets/${target.id}`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "타겟 등록 실패")
  });
  const deleteTarget = useMutation({
    mutationFn: (id: number) => services.targets.delete(id),
    onSuccess: async () => {
      toast.success("타겟을 삭제했습니다.");
      setPendingDelete(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "타겟 삭제 실패")
  });

  return (
    <Section>
      <PageHeader
        title="타겟"
        description="스캔 대상 호스트와 운영 컨텍스트를 관리합니다."
        actions={
          <Button type="button" variant="primary" onClick={() => setCreateOpen(true)}>
            <Plus size={15} />타겟 등록
          </Button>
        }
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Input aria-label="Target host filter" value={host} onChange={(event) => setHost(event.target.value)} placeholder="host filter" />
              <Select aria-label="Target protocol filter" value={protocol} onChange={(event) => setProtocol(event.target.value)}>
                <option value="">All protocols</option>
                {["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </div>
            <span className="muted">Total {targets.data?.total ?? 0}</span>
          </div>
        </CardContent>
      </Card>

      {targets.isLoading ? <LoadingState /> : null}
      {targets.isError ? <ErrorState error={targets.error} onRetry={() => void targets.refetch()} /> : null}
      {targets.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={targets.data.items}
              getRowKey={(target) => target.id}
              empty={<EmptyState title="타겟이 없습니다" description="디스커버리 결과를 승격하거나 직접 등록하세요." />}
              columns={[
                {
                  key: "target",
                  header: "Target",
                  render: (target) => {
                    const model = new TargetModel(target);
                    return <button className="link-button" onClick={() => navigate(`/targets/${target.id}`)}>{model.displayName()}</button>;
                  }
                },
                { key: "host", header: "Host", render: (target) => target.host },
                { key: "endpoint", header: "Endpoint", render: (target) => `${target.transport}/${target.port}` },
                { key: "protocol", header: "Protocol", render: (target) => target.protocol_hint },
                { key: "agent", header: "Agent", render: (target) => (target.agent_enabled ? "enabled" : "disabled") },
                { key: "role", header: "Role", render: (target) => target.context.service_role ?? "-" },
                { key: "created", header: "Created", render: (target) => formatDateTime(target.created_at) },
                {
                  key: "actions",
                  header: "",
                  align: "right",
                  render: (target) => (
                    <Button type="button" size="icon" variant="ghost" onClick={() => setPendingDelete(target)} aria-label={`${new TargetModel(target).displayName()} 삭제`}>
                      <Trash2 size={15} />
                    </Button>
                  )
                }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={createOpen} title="타겟 등록" closeDisabled={createTarget.isPending} onClose={() => !createTarget.isPending && setCreateOpen(false)}>
        <TargetForm
          submitLabel="등록"
          isSubmitting={createTarget.isPending}
          onCancel={() => !createTarget.isPending && setCreateOpen(false)}
          onSubmit={(payload) => createTarget.mutate(payload as Schema<"TargetCreate">)}
        />
      </Dialog>
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="타겟 삭제"
        description={pendingDelete ? `${new TargetModel(pendingDelete).displayName()} (${pendingDelete.host}:${pendingDelete.port}) 타겟을 삭제합니다. 실행 중인 작업이 참조 중이면 서버에서 거절될 수 있습니다.` : ""}
        confirmLabel="삭제"
        pending={deleteTarget.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && deleteTarget.mutate(pendingDelete.id)}
      />
    </Section>
  );
}
