import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import type { AgentRole, Schema } from "../../api/types";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { PageHeader } from "../../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../../components/common/StateViews";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Select } from "../../components/ui/form";
import { DataTable } from "../../components/ui/table";
import { formatDateTime, formatRelative } from "../../lib/format";

type AgentActiveFilter = "all" | "active" | "inactive";
type AgentRoleFilter = "all" | AgentRole;

const agentRoleLabels: Record<AgentRole, string> = {
  host: "Host Agent",
  discovery: "Discovery Agent"
};

function filterToActive(filter: AgentActiveFilter) {
  if (filter === "active") {
    return true;
  }
  if (filter === "inactive") {
    return false;
  }
  return undefined;
}

function pageWithInactiveAgent(page: Schema<"AgentPage">, agentId: string, activeFilter: unknown): Schema<"AgentPage"> {
  const items = page.items.map((agent) => (agent.id === agentId ? { ...agent, active: false } : agent));
  const visibleItems = activeFilter === true ? items.filter((agent) => agent.id !== agentId) : items;
  const removedCount = page.items.length - visibleItems.length;
  return {
    ...page,
    items: visibleItems,
    total: Math.max(0, page.total - removedCount)
  };
}

export function AgentsView() {
  const queryClient = useQueryClient();
  const [pendingDeactivate, setPendingDeactivate] = useState<Schema<"Agent"> | null>(null);
  const [activeFilter, setActiveFilter] = useState<AgentActiveFilter>("all");
  const [roleFilter, setRoleFilter] = useState<AgentRoleFilter>("all");
  const [deactivateError, setDeactivateError] = useState<string | null>(null);
  const active = filterToActive(activeFilter);
  const agentRole = roleFilter === "all" ? undefined : roleFilter;
  const agents = useQuery({
    queryKey: queryKeys.agents.list(active, agentRole),
    queryFn: () => services.agents.list(active, agentRole)
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => services.agents.delete(id),
    onMutate: async (id) => {
      setDeactivateError(null);
      await queryClient.cancelQueries({ queryKey: queryKeys.agents.all });
      const previousAgentPages = queryClient.getQueriesData<Schema<"AgentPage">>({ queryKey: queryKeys.agents.listPrefix });
      const previousAgentDetail = queryClient.getQueryData<Schema<"Agent">>(queryKeys.agents.detail(id));

      previousAgentPages.forEach(([queryKey, page]) => {
        if (!page) {
          return;
        }
        const cachedActiveFilter = Array.isArray(queryKey) ? queryKey[2] : undefined;
        queryClient.setQueryData(queryKey, pageWithInactiveAgent(page, id, cachedActiveFilter));
      });
      if (previousAgentDetail) {
        queryClient.setQueryData(queryKeys.agents.detail(id), { ...previousAgentDetail, active: false });
      }

      return { previousAgentPages, previousAgentDetail };
    },
    onSuccess: async () => {
      toast.success("에이전트를 비활성화했습니다.");
      setPendingDeactivate(null);
    },
    onError: (error, id, context) => {
      context?.previousAgentPages.forEach(([queryKey, page]) => {
        queryClient.setQueryData(queryKey, page);
      });
      if (context?.previousAgentDetail) {
        queryClient.setQueryData(queryKeys.agents.detail(id), context.previousAgentDetail);
      }
      const message = error instanceof Error ? error.message : "비활성화 실패";
      setDeactivateError(message);
      toast.error(message);
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    }
  });

  return (
    <Section>
      <PageHeader
        title="에이전트"
        description="Host Agent와 Discovery Agent 등록 상태를 관리합니다."
      />
      <Card>
        <CardContent>
          <div className="toolbar">
            <div className="toolbar__filters">
              <Select
                aria-label="에이전트 상태 필터"
                value={activeFilter}
                onChange={(event) => setActiveFilter(event.target.value as AgentActiveFilter)}
              >
                <option value="all">전체 상태</option>
                <option value="active">활성</option>
                <option value="inactive">비활성</option>
              </Select>
              <Select
                aria-label="에이전트 역할 필터"
                value={roleFilter}
                onChange={(event) => setRoleFilter(event.target.value as AgentRoleFilter)}
              >
                <option value="all">전체 역할</option>
                <option value="host">Host Agent</option>
                <option value="discovery">Discovery Agent</option>
              </Select>
            </div>
            <span className="muted">전체 {agents.data?.total ?? 0}</span>
          </div>
        </CardContent>
      </Card>
      {agents.isLoading ? <LoadingState /> : null}
      {agents.isError ? <ErrorState error={agents.error} onRetry={() => void agents.refetch()} /> : null}
      {agents.data ? (
        <Card>
          <CardContent>
            <DataTable
              items={agents.data.items}
              getRowKey={(agent) => agent.id}
              empty={<EmptyState title="등록된 에이전트가 없습니다" />}
              columns={[
                { key: "host", header: "호스트명", render: (agent) => agent.hostname },
                { key: "role", header: "역할", render: (agent) => agentRoleLabels[agent.agent_role] ?? agent.agent_role },
                { key: "url", header: "URL", render: (agent) => agent.agent_url },
                {
                  key: "active",
                  header: "상태",
                  render: (agent) => {
                    if (deactivate.isPending && deactivate.variables === agent.id) {
                      return <Badge tone="yellow">비활성화 중</Badge>;
                    }
                    return <Badge tone={agent.active ? "green" : "neutral"}>{agent.active ? "활성" : "비활성"}</Badge>;
                  }
                },
                {
                  key: "stale",
                  header: "하트비트",
                  render: (agent) => (
                    <Badge tone={!agent.active ? "neutral" : agent.is_stale ? "yellow" : "green"}>
                      {!agent.active ? "중지" : agent.is_stale ? "지연" : "정상"}
                    </Badge>
                  )
                },
                { key: "caps", header: "기능", render: (agent) => agent.capabilities.join(", ") },
                { key: "last", header: "마지막 확인", render: (agent) => formatRelative(agent.last_seen) },
                { key: "registered", header: "등록", render: (agent) => formatDateTime(agent.registered_at) },
                {
                  key: "actions",
                  header: "",
                  align: "right",
                  render: (agent) => {
                    const isDeactivating = deactivate.isPending && deactivate.variables === agent.id;
                    return (
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        disabled={!agent.active || deactivate.isPending}
                        onClick={() => {
                          setDeactivateError(null);
                          setPendingDeactivate(agent);
                        }}
                        aria-label={`${agent.hostname} 비활성화`}
                      >
                        {isDeactivating ? <Loader2 className="spin" size={15} /> : <Trash2 size={15} />}
                      </Button>
                    );
                  }
                }
              ]}
            />
          </CardContent>
        </Card>
      ) : null}
      <ConfirmDialog
        open={Boolean(pendingDeactivate)}
        title="에이전트 비활성화"
        description={pendingDeactivate ? `${pendingDeactivate.hostname} 에이전트를 비활성화합니다. 이후 해당 에이전트 기반 작업은 건너뛸 수 있습니다.` : ""}
        confirmLabel={deactivateError ? "다시 시도" : "비활성화"}
        pending={deactivate.isPending}
        error={deactivateError}
        onCancel={() => setPendingDeactivate(null)}
        onConfirm={() => pendingDeactivate && deactivate.mutate(pendingDeactivate.id)}
      />
    </Section>
  );
}
