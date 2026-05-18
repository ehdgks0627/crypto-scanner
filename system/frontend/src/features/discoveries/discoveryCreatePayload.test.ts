import { describe, expect, it } from "vitest";

import { buildDiscoveryCreatePayload, discoveryServiceOptions } from "./discoveryCreatePayload";

const allServiceIds = discoveryServiceOptions.map((service) => service.id);

describe("buildDiscoveryCreatePayload", () => {
  it("builds ports from selected services", () => {
    expect(buildDiscoveryCreatePayload("cidr", " 172.20.0.0/24 ", ["https-web", "ssh", "ipsec"])).toEqual({
      payload: {
        scope_type: "cidr",
        scope_value: "172.20.0.0/24",
        executor_type: "central",
        agent_id: undefined,
        ports: [443, 22, 2222, 500, 4500],
        include_default_ports: false,
        auto_scan: true,
        auto_availability_check: true
      },
      errors: []
    });
  });

  it("covers production-level testbed discovery ports", () => {
    const result = buildDiscoveryCreatePayload("cidr", "172.20.0.0/16", allServiceIds);

    expect(result.payload).not.toBeNull();
    expect(result.payload?.ports?.slice().sort((a, b) => a - b)).toEqual([
      22,
      25,
      443,
      465,
      500,
      587,
      993,
      995,
      2222,
      3306,
      4500,
      5000,
      5432,
      6380,
      8200,
      8443,
      8883,
      9090,
      9093,
      9200,
      9443,
      15017
    ]);
  });

  it("rejects empty service selection", () => {
    const result = buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", []);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("하나 이상의 서비스를 선택하세요.");
  });

  it("resolves combined IP/domain scope values", () => {
    expect(buildDiscoveryCreatePayload("host", "10.0.0.8", ["https-web"]).payload).toMatchObject({
      scope_type: "ip",
      scope_value: "10.0.0.8"
    });
    expect(buildDiscoveryCreatePayload("host", "app.testbed.local", ["https-web"]).payload).toMatchObject({
      scope_type: "domain",
      scope_value: "app.testbed.local"
    });
  });

  it("builds an agent-executed discovery payload", () => {
    const agentId = "9ab79c7e-76e8-4e49-a8b4-40be4d5a2f54";

    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", ["https-web"], "agent", agentId)).toEqual({
      payload: {
        scope_type: "cidr",
        scope_value: "172.20.0.0/24",
        executor_type: "agent",
        agent_id: agentId,
        ports: [443],
        include_default_ports: false,
        auto_scan: true,
        auto_availability_check: true
      },
      errors: []
    });
  });

  it("can disable the follow-up scan and availability pipeline", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", ["https-web"], "central", undefined, false).payload).toMatchObject({
      auto_scan: false,
      auto_availability_check: false
    });
  });

  it("requires a Discovery Agent for agent execution", () => {
    const result = buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", ["https-web"], "agent");

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("Discovery Agent를 선택하세요.");
  });

  it("requires scope value", () => {
    const result = buildDiscoveryCreatePayload("cidr", "", ["https-web"]);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("탐색 대상 값이 필요합니다.");
  });

  it("rejects malformed scope values", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.1", allServiceIds).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("host", "bad/domain", allServiceIds).payload).toBeNull();
  });
});
