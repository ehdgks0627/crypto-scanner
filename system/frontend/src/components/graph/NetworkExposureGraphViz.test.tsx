import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NetworkExposureGraph } from "../../domain/networkExposureGraph";
import { graphNodeAppUrl } from "../../domain/networkExposureGraphDot";
import { NetworkExposureGraphViz } from "./NetworkExposureGraphViz";

const graphvizMock = vi.hoisted(() => ({
  dot: vi.fn(),
  load: vi.fn()
}));

vi.mock("@hpcc-js/wasm/graphviz", () => ({
  Graphviz: {
    load: graphvizMock.load
  }
}));

vi.mock("./NetworkExposureGraph3DView", () => ({
  NetworkExposureGraph3DView: ({ graph }: { graph: NetworkExposureGraph }) => (
    <div className="network-graph-stage network-graph-stage--3d">3D graph nodes {graph.nodes.length}</div>
  )
}));

const targetNode = {
  id: "target:1",
  kind: "target" as const,
  label: "Demo Target",
  subtitle: "10.0.0.1",
  color: "#4b8ca8",
  val: 10,
  riskTier: "HIGH" as const,
  refId: 1,
  assetCount: 1
};

const assetNode = {
  id: "asset:2",
  kind: "asset" as const,
  label: "Replacement Asset",
  subtitle: "certificate",
  color: "#5d8a5a",
  val: 6,
  riskTier: "LOW" as const,
  refId: 2,
  assetCount: 1
};

function graphWith(nodes: NetworkExposureGraph["nodes"]): NetworkExposureGraph {
  return {
    nodes,
    links: [],
    stats: {
      groups: nodes.filter((node) => node.kind === "group").length,
      targets: nodes.filter((node) => node.kind === "target").length,
      endpoints: nodes.filter((node) => node.kind === "endpoint").length,
      assets: nodes.filter((node) => node.kind === "asset").length,
      findings: nodes.filter((node) => node.kind === "finding").length,
      highestRiskTier: nodes[0]?.riskTier
    }
  };
}

function svgForNode(nodeId: string, label: string) {
  return `<svg><g><a href="${graphNodeAppUrl(nodeId)}"><text>${label}</text></a></g></svg>`;
}

describe("NetworkExposureGraphViz", () => {
  beforeEach(() => {
    graphvizMock.dot.mockReset();
    graphvizMock.load.mockReset();
    graphvizMock.dot.mockReturnValue(svgForNode(targetNode.id, targetNode.label));
    graphvizMock.load.mockResolvedValue({ dot: graphvizMock.dot });
  });

  it("stores selected node by id and clears stale selections after graph refresh", async () => {
    const { rerender } = render(<NetworkExposureGraphViz graph={graphWith([targetNode])} />);

    fireEvent.click(await screen.findByText(targetNode.label));

    expect(screen.getByRole("heading", { name: targetNode.label })).toBeInTheDocument();

    graphvizMock.dot.mockReturnValue(svgForNode(assetNode.id, assetNode.label));
    rerender(<NetworkExposureGraphViz graph={graphWith([assetNode])} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "노드를 선택하세요" })).toBeInTheDocument());
  });

  it("uses distinct overlays for data loading errors and Graphviz render errors", async () => {
    const { unmount } = render(<NetworkExposureGraphViz graph={graphWith([targetNode])} error={new Error("api failed")} />);

    expect(await screen.findByText("그래프 데이터를 불러오지 못했습니다")).toBeInTheDocument();

    unmount();
    graphvizMock.dot.mockImplementation(() => {
      throw new Error("dot failed");
    });

    render(<NetworkExposureGraphViz graph={graphWith([targetNode])} />);

    expect(await screen.findByText("Graphviz 그래프를 렌더링하지 못했습니다")).toBeInTheDocument();
  });

  it("zooms the 2D graph and resets the viewport scale", async () => {
    const { container } = render(<NetworkExposureGraphViz graph={graphWith([targetNode])} />);

    await screen.findByText(targetNode.label);

    const graphSvg = container.querySelector(".network-graph-svg") as HTMLElement;
    expect(graphSvg.style.transform).toBe("scale(1)");

    fireEvent.click(screen.getByRole("button", { name: "2D 그래프 확대" }));
    expect(graphSvg.style.transform).toBe("scale(1.15)");
    expect(screen.getByText("115%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "2D 그래프 줌 초기화" }));
    expect(graphSvg.style.transform).toBe("scale(1)");
  });

  it("switches between 2D and 3D graph modes", async () => {
    render(<NetworkExposureGraphViz graph={graphWith([targetNode])} />);

    expect(await screen.findByText(targetNode.label)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "3D" }));

    expect(await screen.findByText("3D graph nodes 1")).toBeInTheDocument();
  });
});
