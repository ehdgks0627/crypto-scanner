import { AlertTriangle, Network, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { GraphCanvas, Svg, lightTheme } from "reagraph";
import type { GraphCanvasRef, GraphEdge, GraphNode, InternalGraphNode, NodeRendererProps, Theme } from "reagraph";

import { relationLabel as displayRelationLabel, riskTierLabel } from "../../domain/displayLabels";
import type { NetworkExposureGraph, NetworkExposureLink, NetworkExposureNode, NetworkExposureNodeKind } from "../../domain/networkExposureGraph";
import { Button } from "../ui/button";

const graphRendererConfig = { preserveDrawingBuffer: true, antialias: true } as const;

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  group: "수집 그룹",
  target: "스캔 대상",
  endpoint: "엔드포인트",
  asset: "암호 자산",
  finding: "위험 발견"
};

const reagraphTheme: Theme = {
  ...lightTheme,
  canvas: {
    ...lightTheme.canvas,
    background: "#ffffff",
    fog: null
  },
  node: {
    ...lightTheme.node,
    fill: "#4b8ca8",
    activeFill: "#111111",
    opacity: 0.92,
    selectedOpacity: 1,
    inactiveOpacity: 0.24,
    label: {
      ...lightTheme.node.label,
      color: "#171717",
      activeColor: "#000000",
      stroke: "#ffffff"
    },
    subLabel: {
      ...lightTheme.node.subLabel,
      color: "#5c5c5c",
      activeColor: "#222222",
      stroke: "#ffffff"
    }
  },
  ring: {
    ...lightTheme.ring,
    fill: "#111111",
    activeFill: "#111111"
  },
  edge: {
    ...lightTheme.edge,
    fill: "#8a8a8a",
    activeFill: "#111111",
    opacity: 0.68,
    selectedOpacity: 1,
    inactiveOpacity: 0.18,
    label: {
      ...lightTheme.edge.label,
      color: "#565656",
      activeColor: "#111111",
      fontSize: 9
    }
  },
  arrow: {
    ...lightTheme.arrow,
    fill: "#8a8a8a",
    activeFill: "#111111"
  },
  lasso: {
    background: "rgba(75, 140, 168, 0.12)",
    border: "#4b8ca8"
  }
};

export function NetworkExposureGraph3DView({
  graph,
  isLoading,
  isFetching,
  error,
  selectedNodeId,
  onRetry,
  onSelectNode
}: {
  graph: NetworkExposureGraph;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  selectedNodeId?: string;
  onRetry?: () => void;
  onSelectNode: (nodeId: string | undefined) => void;
}) {
  const graphRef = useRef<GraphCanvasRef | null>(null);
  const canUseWebGl = useWebGlAvailability();
  const theme = useGraphTheme();
  const hasGraph = graph.nodes.length > 0;
  const nodes = useMemo(() => graph.nodes.map(toReagraphNode), [graph.nodes]);
  const edges = useMemo(() => graph.links.map(toReagraphEdge), [graph.links]);
  const selections = selectedNodeId ? [selectedNodeId] : [];

  useEffect(() => {
    if (!hasGraph || !canUseWebGl) {
      return undefined;
    }
    const timer = window.setTimeout(() => graphRef.current?.fitNodesInView(), 300);
    return () => window.clearTimeout(timer);
  }, [canUseWebGl, hasGraph, nodes, edges]);

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }
    graphRef.current?.fitNodesInView([selectedNodeId]);
  }, [selectedNodeId]);

  return (
    <div className="network-graph-stage network-graph-stage--3d">
      {hasGraph && canUseWebGl ? (
        <>
          <div className="network-graph-reagraph">
            <GraphCanvas
              ref={graphRef}
              nodes={nodes}
              edges={edges}
              layoutType="forceDirected3d"
              cameraMode="rotate"
              sizingType="default"
              labelType="all"
              edgeLabelPosition="inline"
              edgeArrowPosition="end"
              edgeInterpolation="curved"
              selections={selections}
              actives={selections}
              defaultNodeSize={11}
              minNodeSize={8}
              maxNodeSize={23}
              draggable
              animated
              glOptions={graphRendererConfig}
              theme={theme}
              renderNode={GraphNodeIcon}
              onCanvasClick={() => onSelectNode(undefined)}
              onNodeClick={(node) => {
                onSelectNode(node.id);
                graphRef.current?.fitNodesInView([node.id]);
              }}
            />
          </div>
          <div className="network-graph-canvas-controls">
            <Button type="button" size="icon" variant="ghost" aria-label="3D 그래프 보기 초기화" onClick={() => graphRef.current?.fitNodesInView()}>
              <RotateCcw size={15} />
            </Button>
          </div>
        </>
      ) : null}

      {!hasGraph ? <GraphOverlay icon={<Network size={18} />} label="표시할 그래프 데이터가 없습니다" /> : null}
      {hasGraph && !canUseWebGl ? <GraphOverlay label="이 브라우저에서는 3D WebGL 그래프를 사용할 수 없습니다" /> : null}
      {isLoading ? <GraphOverlay label="네트워크 그래프 불러오는 중" /> : null}
      {error ? <GraphErrorOverlay onRetry={onRetry} /> : null}
      {isFetching && !isLoading ? <span className="network-graph-refresh">동기화 중</span> : null}
    </div>
  );
}

function toReagraphNode(node: NetworkExposureNode): GraphNode {
  return {
    id: node.id,
    label: node.label,
    subLabel: nodeSubLabel(node),
    size: Math.max(8, Math.min(23, node.val * 1.25)),
    fill: node.color,
    labelVisible: true,
    cluster: node.kind,
    icon: nodeIconUri(node.kind, node.color),
    data: {
      kind: node.kind,
      riskTier: node.riskTier,
      assetCount: node.assetCount
    }
  };
}

function toReagraphEdge(link: NetworkExposureLink): GraphEdge {
  return {
    id: link.id,
    source: link.source,
    target: link.target,
    label: relationLabel(link.label),
    size: Math.max(1, link.width),
    fill: link.color,
    data: {
      kind: link.kind
    }
  };
}

function GraphNodeIcon(props: NodeRendererProps) {
  const icon = props.node.icon ?? nodeIconUri(nodeKindFor(props.node), String(props.color));
  return <Svg {...props} image={icon} />;
}

function nodeKindFor(node: InternalGraphNode): NetworkExposureNodeKind {
  const kind = node.data?.kind;
  return kind === "group" || kind === "target" || kind === "endpoint" || kind === "asset" || kind === "finding" ? kind : "asset";
}

function nodeSubLabel(node: NetworkExposureNode) {
  return [kindLabels[node.kind], node.subtitle, node.riskTier ? riskTierLabel(node.riskTier) : undefined].filter(Boolean).join(" · ");
}

function relationLabel(label: string) {
  return displayRelationLabel(label);
}

function GraphOverlay({ label, icon }: { label: string; icon?: ReactNode }) {
  return (
    <div className="network-graph-overlay">
      {icon ?? <Network size={18} />}
      <span>{label}</span>
    </div>
  );
}

function GraphErrorOverlay({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="network-graph-overlay network-graph-overlay--error" role="alert">
      <AlertTriangle size={18} />
      <span>그래프 데이터를 불러오지 못했습니다</span>
      {onRetry ? (
        <Button type="button" size="sm" onClick={onRetry}>
          재시도
        </Button>
      ) : null}
    </div>
  );
}

function useWebGlAvailability() {
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    setSupported(isWebGlSupported());
  }, []);

  return supported;
}

function useGraphTheme() {
  const [theme, setTheme] = useState(reagraphTheme);

  useEffect(() => {
    const updateTheme = () => {
      const styles = window.getComputedStyle(document.documentElement);
      const panel = readCssColor(styles, "--panel", "#ffffff");
      const text = readCssColor(styles, "--text", "#171717");
      const textSoft = readCssColor(styles, "--text-soft", "#565656");
      const border = readCssColor(styles, "--border", "#d2d2d2");
      const primary = readCssColor(styles, "--primary", "#111111");

      setTheme({
        ...reagraphTheme,
        canvas: {
          ...reagraphTheme.canvas,
          background: panel
        },
        node: {
          ...reagraphTheme.node,
          activeFill: primary,
          label: {
            ...reagraphTheme.node.label,
            color: text,
            activeColor: primary,
            stroke: panel
          },
          subLabel: {
            ...reagraphTheme.node.subLabel,
            color: textSoft,
            activeColor: text,
            stroke: panel
          }
        },
        ring: {
          ...reagraphTheme.ring,
          fill: primary,
          activeFill: primary
        },
        edge: {
          ...reagraphTheme.edge,
          activeFill: primary,
          label: {
            ...reagraphTheme.edge.label,
            color: textSoft,
            activeColor: text
          }
        },
        arrow: {
          ...reagraphTheme.arrow,
          activeFill: primary
        },
        lasso: {
          background: colorWithAlpha(border, 0.16),
          border
        }
      });
    };

    updateTheme();
    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return theme;
}

function readCssColor(styles: CSSStyleDeclaration, variable: string, fallback: string) {
  return styles.getPropertyValue(variable).trim() || fallback;
}

function colorWithAlpha(color: string, alpha: number) {
  const hexMatch = color.match(/^#([0-9a-f]{6})$/i);
  if (!hexMatch) {
    return color;
  }
  const value = hexMatch[1];
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function isWebGlSupported() {
  if (typeof window === "undefined" || typeof document === "undefined" || typeof WebGLRenderingContext === "undefined") {
    return false;
  }
  const canvas = document.createElement("canvas");
  return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
}

function nodeIconUri(kind: NetworkExposureNodeKind, color: string) {
  const stroke = normalizeHexColor(color);
  const svgByKind: Record<NetworkExposureNodeKind, string> = {
    group: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48"><path d="M7 14h17l5 6h28v22H7z" fill="#ffffff" stroke="${stroke}" stroke-width="4" stroke-linejoin="round"/><path d="M15 28h34M15 35h25" stroke="#171717" stroke-width="3" stroke-linecap="round"/></svg>`,
    target: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48"><rect x="7" y="8" width="50" height="32" rx="5" fill="#ffffff" stroke="${stroke}" stroke-width="4"/><path d="M15 18h18M15 29h26" stroke="#171717" stroke-width="3" stroke-linecap="round"/><circle cx="48" cy="18" r="3" fill="${stroke}"/><circle cx="48" cy="30" r="3" fill="${stroke}"/></svg>`,
    endpoint: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48"><rect x="10" y="11" width="44" height="26" rx="13" fill="#ffffff" stroke="${stroke}" stroke-width="4"/><path d="M18 24h28M25 17l-7 7 7 7M39 17l7 7-7 7" fill="none" stroke="#171717" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    asset: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48"><path d="M25 23a10 10 0 1 1 6 9l-5 5h-6v-6h-6v-6h8z" fill="#ffffff" stroke="${stroke}" stroke-width="4" stroke-linejoin="round"/><circle cx="39" cy="19" r="3" fill="#171717"/></svg>`,
    finding: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 48"><path d="M32 5 59 43H5z" fill="#ffffff" stroke="${stroke}" stroke-width="4" stroke-linejoin="round"/><path d="M32 18v11" stroke="#171717" stroke-width="4" stroke-linecap="round"/><circle cx="32" cy="36" r="2.8" fill="#171717"/></svg>`
  };
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgByKind[kind])}`;
}

function normalizeHexColor(color: string) {
  if (/^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(color)) {
    return color;
  }
  return "#4b8ca8";
}
