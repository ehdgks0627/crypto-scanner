import { describe, expect, it } from "vitest";

import type { Schema } from "../api/types";
import { buildNetworkExposureGraph } from "./networkExposureGraph";

const baseTarget: Schema<"Target"> = {
  id: 10,
  host: "web.testbed.local",
  display_name: "Web Server (RSA)",
  ip: "10.10.10.21",
  port: 443,
  protocol_hint: "TLS",
  sni: null,
  transport: "TCP",
  agent_enabled: false,
  agent_url: null,
  context: {
    sensitivity: null,
    lifespan_years: null,
    criticality: null,
    exposure: null,
    service_role: null
  },
  created_at: "2026-04-30T00:00:00Z",
  updated_at: "2026-04-30T00:00:00Z"
};

function asset(overrides: Partial<Schema<"AssetListItem">>): Schema<"AssetListItem"> {
  return {
    id: 100,
    snapshot_id: 1,
    bom_ref: "tls:web:leaf:rsa",
    asset_class: "crypto",
    asset_type: "certificate",
    name: "web.testbed.local TLS leaf certificate",
    target_id: 10,
    target_label: "web.testbed.local:443",
    summary: { algorithm: "RSA-2048", algorithm_family: "RSA" },
    risk: { score: 82, tier: "HIGH" },
    ...overrides
  };
}

describe("buildNetworkExposureGraph", () => {
  it("builds target, endpoint, asset, and finding relationships", () => {
    const graph = buildNetworkExposureGraph([asset({})], [baseTarget]);

    expect(graph.nodes.map((node) => node.id)).toEqual([
      "group:target-scope:10.10.10.0/24",
      "target:10",
      "endpoint:10:TCP:443",
      "asset:100",
      "finding:HIGH"
    ]);
    expect(graph.nodes.find((node) => node.id === "group:target-scope:10.10.10.0/24")?.label).toBe("10.10.10.0/24");
    expect(graph.nodes.find((node) => node.id === "target:10")?.label).toBe("Web Server (RSA)");
    expect(graph.links.map((link) => [link.kind, link.source, link.target])).toEqual([
      ["contains", "group:target-scope:10.10.10.0/24", "target:10"],
      ["exposes", "target:10", "endpoint:10:TCP:443"],
      ["presents", "endpoint:10:TCP:443", "asset:100"],
      ["has_finding", "asset:100", "finding:HIGH"]
    ]);
    expect(graph.stats).toMatchObject({ groups: 1, targets: 1, endpoints: 1, assets: 1, findings: 1, highestRiskTier: "HIGH" });
  });

  it("deduplicates shared endpoint links and promotes the highest endpoint risk", () => {
    const graph = buildNetworkExposureGraph(
      [
        asset({ id: 100, risk: { score: 52, tier: "MEDIUM" } }),
        asset({ id: 101, asset_type: "protocol", name: "web.testbed.local key agreement", risk: { score: 91, tier: "CRITICAL" } })
      ],
      [baseTarget]
    );

    expect(graph.links.filter((link) => link.kind === "exposes")).toHaveLength(1);
    expect(graph.links.filter((link) => link.kind === "contains")).toHaveLength(1);
    expect(graph.nodes.find((node) => node.id === "endpoint:10:TCP:443")?.riskTier).toBe("CRITICAL");
    expect(graph.nodes.find((node) => node.id === "finding:CRITICAL")?.assetCount).toBe(1);
    expect(graph.stats.highestRiskTier).toBe("CRITICAL");
  });

  it("groups discovery scope targets and host agent targets differently", () => {
    const discoveryTarget: Schema<"Target"> = {
      ...baseTarget,
      graph_group: {
        kind: "discovery_scope",
        key: "discovery:cidr:172.20.0.0/16:agent-1",
        label: "172.20.0.0/16",
        subtitle: "Discovery Agent · CIDR"
      }
    };
    const hostAgentTarget: Schema<"Target"> = {
      ...baseTarget,
      id: 11,
      host: "ssh.testbed.local",
      display_name: "SSH Server",
      ip: "10.10.10.22",
      port: 22,
      protocol_hint: "SSH",
      agent_enabled: true
    };
    const graph = buildNetworkExposureGraph(
      [
        asset({ id: 100, target_id: discoveryTarget.id }),
        asset({ id: 101, target_id: hostAgentTarget.id, target_label: "ssh.testbed.local:22", name: "ssh.testbed.local host key" })
      ],
      [discoveryTarget, hostAgentTarget]
    );

    expect(graph.nodes.find((node) => node.id === "group:discovery:cidr:172.20.0.0/16:agent-1")?.label).toBe("172.20.0.0/16");
    expect(graph.nodes.find((node) => node.id === "group:host:ssh.testbed.local")?.label).toBe("SSH Server");
    expect(graph.stats.groups).toBe(2);
  });
});
