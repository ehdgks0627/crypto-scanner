import { describe, expect, it } from "vitest";

import type { NetworkExposureGraph } from "./networkExposureGraph";
import { buildNetworkExposureDot, graphNodeAppUrl, parseGraphNodeAppUrl } from "./networkExposureGraphDot";

const graph: NetworkExposureGraph = {
  nodes: [
    {
      id: "target:10",
      kind: "target",
      label: "Web Server (RSA)",
      subtitle: "10.10.10.21",
      color: "#d18a3a",
      val: 12,
      riskTier: "HIGH",
      refId: 10,
      assetCount: 2
    },
    {
      id: "endpoint:10:TCP:443",
      kind: "endpoint",
      label: "web.testbed.local:443/TLS",
      subtitle: "TCP",
      color: "#d18a3a",
      val: 10,
      riskTier: "HIGH",
      refId: 10,
      assetCount: 2
    },
    {
      id: "asset:100",
      kind: "asset",
      label: "web.testbed.local TLS leaf certificate",
      subtitle: "certificate · RSA-2048 · RSA",
      color: "#d18a3a",
      val: 8,
      riskTier: "HIGH",
      refId: 100,
      assetCount: 1
    },
    {
      id: "finding:HIGH",
      kind: "finding",
      label: "HIGH finding",
      subtitle: "risk tier",
      color: "#d18a3a",
      val: 8,
      riskTier: "HIGH",
      assetCount: 1
    }
  ],
  links: [
    { id: "e1", source: "target:10", target: "endpoint:10:TCP:443", kind: "exposes", label: "exposes", color: "#4b8ca8", width: 1.7 },
    { id: "e2", source: "endpoint:10:TCP:443", target: "asset:100", kind: "presents", label: "presents", color: "#6d5a9a", width: 1.7 },
    { id: "e3", source: "asset:100", target: "finding:HIGH", kind: "has_finding", label: "has finding", color: "#c4413a", width: 2.2 }
  ],
  stats: { targets: 1, endpoints: 1, assets: 1, findings: 1, highestRiskTier: "HIGH" }
};

describe("buildNetworkExposureDot", () => {
  it("emits Graphviz nodes with meaningful shapes and edge labels", () => {
    const dot = buildNetworkExposureDot(graph);

    expect(dot).toContain("graph NetworkExposure");
    expect(dot).toContain("layout=sfdp");
    expect(dot).toContain("splines=true");
    expect(dot).toContain("shape=box3d");
    expect(dot).toContain("shape=component");
    expect(dot).toContain("shape=note");
    expect(dot).toContain("shape=octagon");
    expect(dot).toContain('label="노출"');
    expect(dot).toContain('label="제공"');
    expect(dot).toContain('label="위험 발견"');
    expect(dot).toContain('style="dashed"');
    expect(dot).toContain('"target:10" -- "endpoint:10:TCP:443"');
    expect(dot).not.toContain("rank=same");
  });

  it("round-trips app node URLs", () => {
    const href = graphNodeAppUrl("endpoint:10:TCP:443");

    expect(href).toBe("#graph-node:endpoint%3A10%3ATCP%3A443");
    expect(parseGraphNodeAppUrl(href)).toBe("endpoint:10:TCP:443");
    expect(parseGraphNodeAppUrl("#graph-node:%E0%A4%A")).toBeUndefined();
    expect(parseGraphNodeAppUrl("https://example.test")).toBeUndefined();
  });

  it("escapes DOT ids and labels without breaking node links", () => {
    const dot = buildNetworkExposureDot({
      nodes: [
        {
          id: 'target:"quoted"\\node',
          kind: "target",
          label: 'Target "quoted" \\ slash\n<script>',
          subtitle: "line\rbreak & percent %",
          color: "#9a9a9a",
          val: 8,
          riskTier: undefined,
          refId: 20,
          assetCount: 1
        }
      ],
      links: [],
      stats: { targets: 1, endpoints: 0, assets: 0, findings: 0, highestRiskTier: undefined }
    });

    expect(dot).toContain('"target:\\"quoted\\"\\\\node"');
    expect(dot).toContain('Target \\"quoted\\" \\\\ slash\\n<script>');
    expect(dot).toContain("linebreak & percent %");
    expect(dot).toContain('URL="#graph-node:target%3A%22quoted%22%5Cnode"');
  });
});
