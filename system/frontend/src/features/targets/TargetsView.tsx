import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
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
import { Input, Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { enabledLabel } from "../../domain/displayLabels";
import { TargetModel } from "../../domain/models";
import { formatDateTime } from "../../lib/format";

export function TargetsView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<Schema<"Target"> | null>(null);
  const [host, setHost] = useState("");
  const [protocol, setProtocol] = useState("");
  const filters = useMemo(() => ({ host: host || undefined, protocol_hint: protocol || undefined, limit: 100 }), [host, protocol]);
  const targets = useQuery({
    queryKey: queryKeys.targets.list(filters),
    queryFn: () => services.targets.list(filters)
  });
  const deleteTarget = useMutation({
    mutationFn: (id: number) => services.targets.delete(id),
    onSuccess: async () => {
      toast.success("스캔 대상을 삭제했습니다.");
      setPendingDelete(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.targets.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "스캔 대상 삭제 실패")
  });

  return (
    <Section>
      <PageHeader
        title="스캔 대상"
        description="탐색 대상 결과에서 자동 등록된 엔드포인트를 스캔 가능한 대상으로 관리합니다."
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Input aria-label="스캔 대상 호스트 필터" value={host} onChange={(event) => setHost(event.target.value)} placeholder="호스트 검색" />
              <Select aria-label="스캔 대상 프로토콜 필터" value={protocol} onChange={(event) => setProtocol(event.target.value)}>
                <option value="">전체 프로토콜</option>
                {["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </div>
            <span className="muted">전체 {targets.data?.total ?? 0}</span>
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
              empty={<EmptyState title="스캔 대상이 없습니다" description="탐색 대상에서 엔드포인트를 찾으면 스캔 대상으로 자동 등록됩니다." />}
              columns={[
                {
                  key: "target",
                  header: "스캔 대상",
                  render: (target) => {
                    const model = new TargetModel(target);
                    return <button className="link-button" onClick={() => navigate(`/targets/${target.id}`)}>{model.displayName()}</button>;
                  }
                },
                { key: "host", header: "호스트", render: (target) => target.host },
                { key: "endpoint", header: "엔드포인트", render: (target) => `${target.transport}/${target.port}` },
                { key: "protocol", header: "프로토콜", render: (target) => target.protocol_hint },
                { key: "agent", header: "에이전트", render: (target) => enabledLabel(target.agent_enabled) },
                { key: "role", header: "역할", render: (target) => target.context.service_role ?? "-" },
                { key: "created", header: "생성", render: (target) => formatDateTime(target.created_at) },
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

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="스캔 대상 삭제"
        description={pendingDelete ? `${new TargetModel(pendingDelete).displayName()} (${pendingDelete.host}:${pendingDelete.port}) 스캔 대상을 삭제합니다. 실행 중인 작업이 참조 중이면 서버에서 거절될 수 있습니다.` : ""}
        confirmLabel="삭제"
        pending={deleteTarget.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && deleteTarget.mutate(pendingDelete.id)}
      />
    </Section>
  );
}
