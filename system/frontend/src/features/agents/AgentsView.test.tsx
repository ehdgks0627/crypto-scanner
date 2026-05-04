import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/client";
import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { AgentsView } from "./AgentsView";

function agent(overrides: Partial<Schema<"Agent">> = {}): Schema<"Agent"> {
  return {
    id: "9ab79c7e-76e8-4e49-a8b4-40be4d5a2f54",
    hostname: "agent-a.testbed.local",
    agent_role: "host",
    agent_url: "http://agent-a.testbed.local:9100/",
    capabilities: ["agent.cert_store"],
    os_distribution: "ubuntu-22.04",
    registered_at: "2026-04-29T00:00:00Z",
    token_rotated_at: "2026-04-29T00:00:00Z",
    last_seen: "2026-04-29T00:01:00Z",
    active: true,
    is_stale: false,
    ...overrides
  };
}

function agentPage(items: Schema<"Agent">[]): Schema<"AgentPage"> {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 100
  };
}

describe("AgentsView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("immediately reflects an agent deactivation in the table", async () => {
    const user = userEvent.setup();
    const activeAgent = agent();
    let resolveDelete: () => void = () => {};
    vi.spyOn(services.agents, "list")
      .mockResolvedValueOnce(agentPage([activeAgent]))
      .mockResolvedValue(agentPage([{ ...activeAgent, active: false }]));
    vi.spyOn(services.agents, "delete").mockReturnValue(
      new Promise<void>((resolve) => {
        resolveDelete = resolve;
      })
    );

    renderWithApp(<AgentsView />);

    expect(await screen.findByText("agent-a.testbed.local")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "agent-a.testbed.local 비활성화" }));
    await user.click(screen.getByRole("button", { name: "비활성화" }));

    expect(await screen.findByText("비활성화 중")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "agent-a.testbed.local 비활성화" })).toBeDisabled();

    resolveDelete();

    await waitFor(() => expect(screen.getByText("비활성")).toBeInTheDocument());
    expect(screen.getByText("중지")).toBeInTheDocument();
  });

  it("keeps the dialog open with a retry action when deactivation fails", async () => {
    const user = userEvent.setup();
    const activeAgent = agent();
    vi.spyOn(services.agents, "list").mockResolvedValue(agentPage([activeAgent]));
    vi.spyOn(services.agents, "delete").mockRejectedValue(
      new ApiError("서버에서 비활성화를 거절했습니다.", { status: 500 })
    );

    renderWithApp(<AgentsView />);

    await screen.findByText("agent-a.testbed.local");
    await user.click(screen.getByRole("button", { name: "agent-a.testbed.local 비활성화" }));
    await user.click(screen.getByRole("button", { name: "비활성화" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("서버에서 비활성화를 거절했습니다.");
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeEnabled();
    expect(screen.getAllByText("활성").length).toBeGreaterThan(0);
  });

  it("requests the selected active-state filter", async () => {
    const user = userEvent.setup();
    const list = vi.spyOn(services.agents, "list").mockImplementation(async (active) => {
      const activeAgent = agent();
      const inactiveAgent = agent({
        id: "57373b7e-1d73-4ae7-baad-1571f8af9261",
        hostname: "inactive-agent.testbed.local",
        active: false
      });
      if (active === true) {
        return agentPage([activeAgent]);
      }
      if (active === false) {
        return agentPage([inactiveAgent]);
      }
      return agentPage([activeAgent, inactiveAgent]);
    });

    renderWithApp(<AgentsView />);

    expect(await screen.findByText("inactive-agent.testbed.local")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("에이전트 상태 필터"), "active");

    await waitFor(() => expect(list).toHaveBeenLastCalledWith(true, undefined));
    expect(screen.queryByText("inactive-agent.testbed.local")).not.toBeInTheDocument();
  });

  it("requests the selected role filter", async () => {
    const user = userEvent.setup();
    const list = vi.spyOn(services.agents, "list").mockImplementation(async (_active, role) => {
      const hostAgent = agent();
      const discoveryAgent = agent({
        id: "2a189f55-b431-42ba-a7f0-52c4fdb0839c",
        hostname: "probe.dmz.testbed.local",
        agent_role: "discovery",
        capabilities: ["agent.discovery"]
      });
      if (role === "discovery") {
        return agentPage([discoveryAgent]);
      }
      return agentPage([hostAgent, discoveryAgent]);
    });

    renderWithApp(<AgentsView />);

    expect(await screen.findByText("probe.dmz.testbed.local")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("에이전트 역할 필터"), "discovery");

    await waitFor(() => expect(list).toHaveBeenLastCalledWith(undefined, "discovery"));
    expect(screen.queryByText("agent-a.testbed.local")).not.toBeInTheDocument();
    expect(screen.getAllByText("Discovery Agent").length).toBeGreaterThan(0);
  });
});
