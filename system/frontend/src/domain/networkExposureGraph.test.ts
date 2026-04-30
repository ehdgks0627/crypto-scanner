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
      "target:10",
      "endpoint:10:TCP:443",
      "asset:100",
      "finding:HIGH"
    ]);
    expect(graph.nodes.find((node) => node.id === "target:10")?.label).toBe("Web Server (RSA)");
    expect(graph.links.map((link) => [link.kind, link.source, link.target])).toEqual([
      ["exposes", "target:10", "endpoint:10:TCP:443"],
      ["presents", "endpoint:10:TCP:443", "asset:100"],
      ["has_finding", "asset:100", "finding:HIGH"]
    ]);
    expect(graph.stats).toMatchObject({ targets: 1, endpoints: 1, assets: 1, findings: 1, highestRiskTier: "HIGH" });
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
    expect(graph.nodes.find((node) => node.id === "endpoint:10:TCP:443")?.riskTier).toBe("CRITICAL");
    expect(graph.nodes.find((node) => node.id === "finding:CRITICAL")?.assetCount).toBe(1);
    expect(graph.stats.highestRiskTier).toBe("CRITICAL");
  });
});
