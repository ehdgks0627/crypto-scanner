import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { DataTable } from "../../components/ui/table";
import { formatDateTime, formatRelative } from "../../lib/format";

export function AgentsView() {
  const queryClient = useQueryClient();
  const [pendingDeactivate, setPendingDeactivate] = useState<Schema<"Agent"> | null>(null);
  const agents = useQuery({
    queryKey: queryKeys.agents.list(),
    queryFn: () => services.agents.list()
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => services.agents.delete(id),
    onSuccess: async () => {
      toast.success("에이전트를 비활성화했습니다.");
      setPendingDeactivate(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "비활성화 실패")
  });

  return (
    <Section>
      <PageHeader
        title="Agents"
        description="호스트 내부 스캐너 에이전트 등록 상태를 관리합니다."
      />
      {agents.isLoading ? <LoadingState /> : null}
      {agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} /> : null}
      {agents.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={agents.data.items}
              getRowKey={(agent) => agent.id}
              empty={<EmptyState title="등록된 Agent가 없습니다" />}
              columns={[
                { key: "host", header: "Hostname", render: (agent) => agent.hostname },
                { key: "url", header: "URL", render: (agent) => agent.agent_url },
                { key: "active", header: "Active", render: (agent) => (agent.active ? "yes" : "no") },
                { key: "stale", header: "Stale", render: (agent) => (agent.is_stale ? "yes" : "no") },
                { key: "caps", header: "Capabilities", render: (agent) => agent.capabilities.join(", ") },
                { key: "last", header: "Last Seen", render: (agent) => formatRelative(agent.last_seen) },
                { key: "registered", header: "Registered", render: (agent) => formatDateTime(agent.registered_at) },
                {
                  key: "actions",
                  header: "",
                  align: "right",
                  render: (agent) => (
                    <Button type="button" size="icon" variant="ghost" onClick={() => setPendingDeactivate(agent)} aria-label={`${agent.hostname} 비활성화`}>
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
        open={Boolean(pendingDeactivate)}
        title="Agent 비활성화"
        description={pendingDeactivate ? `${pendingDeactivate.hostname} Agent를 비활성화합니다. 이후 해당 Agent 기반 scanner는 skip될 수 있습니다.` : ""}
        confirmLabel="비활성화"
        pending={deactivate.isPending}
        onCancel={() => setPendingDeactivate(null)}
        onConfirm={() => pendingDeactivate && deactivate.mutate(pendingDeactivate.id)}
      />
    </Section>
  );
}
