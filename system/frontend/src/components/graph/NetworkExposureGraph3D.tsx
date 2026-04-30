import { AlertTriangle, Box, Crosshair, ExternalLink, Network } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ForceGraphMethods } from "react-force-graph-3d";

import type { NetworkExposureGraph, NetworkExposureLink, NetworkExposureNode, NetworkExposureNodeKind } from "../../domain/networkExposureGraph";
import { formatDateTime, formatNumber } from "../../lib/format";
import { Button } from "../ui/button";

const ForceGraph3D = lazy(() => import("react-force-graph-3d"));

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  target: "Target",
  endpoint: "Endpoint",
  asset: "Crypto Asset",
  finding: "Finding"
};

const graphRendererConfig = { preserveDrawingBuffer: true, antialias: true } as const;

type RenderNode = NetworkExposureNode & {
  x?: number;
  y?: number;
  z?: number;
};

export function NetworkExposureGraph3D({
  graph,
  isLoading,
  isFetching,
  error,
  updatedAt,
  onRetry,
  onOpenNode
}: {
  graph: NetworkExposureGraph;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  updatedAt?: number;
  onRetry?: () => void;
  onOpenNode?: (node: NetworkExposureNode) => void;
}) {
  const graphRef = useRef<ForceGraphMethods>();
  const [stageRef, size] = useElementSize<HTMLDivElement>();
  const [selectedNode, setSelectedNode] = useState<NetworkExposureNode | undefined>();
  const canUseWebGl = useWebGlAvailability();
  const graphTheme = useGraphTheme();
  const graphData = useMemo(() => ({ nodes: graph.nodes, links: graph.links }), [graph.links, graph.nodes]);
  const lastUpdated = updatedAt ? formatDateTime(new Date(updatedAt).toISOString()) : "-";
  const hasGraph = graph.nodes.length > 0;

  return (
    <section className="network-graph-band" aria-labelledby="network-graph-title">
      <div className="network-graph-band__header">
        <div>
          <span className="page-header__eyebrow">LIVE EXPOSURE GRAPH</span>
          <h2 id="network-graph-title">네트워크 암호 노출 현황</h2>
        </div>
        <div className="network-graph-stats" aria-label="Network graph summary">
          <span>Targets {formatNumber(graph.stats.targets)}</span>
          <span>Endpoints {formatNumber(graph.stats.endpoints)}</span>
          <span>Assets {formatNumber(graph.stats.assets)}</span>
          <span>Findings {formatNumber(graph.stats.findings)}</span>
        </div>
      </div>

      <div className="network-graph-layout">
        <div className="network-graph-stage" ref={stageRef}>
          {hasGraph && canUseWebGl ? (
            <Suspense fallback={<GraphOverlay label="그래프 준비 중" />}>
              <ForceGraph3D
                ref={graphRef}
                graphData={graphData}
                width={Math.max(size.width, 320)}
                height={Math.max(size.height, 360)}
                backgroundColor={graphTheme.background}
                rendererConfig={graphRendererConfig}
                showNavInfo={false}
                nodeRelSize={5.5}
                nodeResolution={16}
                nodeVal={(node) => (node as NetworkExposureNode).val}
                nodeColor={(node) => (node as NetworkExposureNode).color}
                nodeLabel={(node) => nodeLabel(node as NetworkExposureNode)}
                linkLabel={(link) => linkLabel(link as NetworkExposureLink)}
                linkColor={(link) => (link as NetworkExposureLink).color}
                linkWidth={(link) => (link as NetworkExposureLink).width}
                linkOpacity={0.78}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={0.88}
                linkDirectionalParticles={(link) => ((link as NetworkExposureLink).kind === "exposes" ? 3 : 1)}
                linkDirectionalParticleSpeed={0.004}
                linkDirectionalParticleWidth={2.4}
                cooldownTicks={120}
                d3VelocityDecay={0.34}
                dagMode="radialout"
                dagLevelDistance={110}
                onEngineStop={() => graphRef.current?.zoomToFit(500, 12)}
                onNodeClick={(node) => {
                  const selected = node as RenderNode;
                  setSelectedNode(selected);
                  focusNode(graphRef.current, selected);
                }}
              />
            </Suspense>
          ) : null}

          {!hasGraph ? <GraphOverlay icon={<Network size={18} />} label="표시할 그래프 데이터가 없습니다" /> : null}
          {hasGraph && !canUseWebGl ? <StaticGraphFallback graph={graph} /> : null}
          {isLoading ? <GraphOverlay label="네트워크 그래프 불러오는 중" /> : null}
          {error ? <GraphErrorOverlay onRetry={onRetry} /> : null}
          {isFetching && !isLoading ? <span className="network-graph-refresh">syncing</span> : null}
        </div>

        <aside className="network-graph-inspector" aria-label="Selected graph node">
          <div>
            <span className="network-graph-inspector__eyebrow">Selected</span>
            <h3>{selectedNode?.label ?? "노드를 선택하세요"}</h3>
            {selectedNode ? <p>{nodeLabel(selectedNode)}</p> : <p>최근 관측 기준 {lastUpdated}</p>}
          </div>
          {selectedNode ? (
            <dl className="network-graph-meta">
              <div>
                <dt>Type</dt>
                <dd>{kindLabels[selectedNode.kind]}</dd>
              </div>
              <div>
                <dt>Risk</dt>
                <dd>{selectedNode.riskTier ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Assets</dt>
                <dd>{formatNumber(selectedNode.assetCount)}</dd>
              </div>
            </dl>
          ) : (
            <GraphLegend />
          )}
          {selectedNode && onOpenNode ? (
            <Button type="button" size="sm" onClick={() => onOpenNode(selectedNode)}>
              <ExternalLink size={14} />열기
            </Button>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function GraphLegend() {
  return (
    <div className="network-graph-legend" aria-label="Graph legend">
      <span><i className="is-target" />Target</span>
      <span><i className="is-endpoint" />Endpoint</span>
      <span><i className="is-asset" />Crypto Asset</span>
      <span><i className="is-finding" />Finding</span>
    </div>
  );
}

function StaticGraphFallback({ graph }: { graph: NetworkExposureGraph }) {
  return (
    <div className="network-graph-static" role="img" aria-label="Static network exposure graph">
      {graph.nodes.slice(0, 12).map((node) => (
        <span key={node.id} className={`network-graph-static__node is-${node.kind}`}>
          {node.kind === "finding" ? <AlertTriangle size={14} /> : node.kind === "asset" ? <Box size={14} /> : <Crosshair size={14} />}
          {node.label}
        </span>
      ))}
    </div>
  );
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

function nodeLabel(node: NetworkExposureNode) {
  return [kindLabels[node.kind], node.label, node.subtitle, node.riskTier].filter(Boolean).join(" · ");
}

function linkLabel(link: NetworkExposureLink) {
  return link.label;
}

function focusNode(graph: ForceGraphMethods | undefined, node: RenderNode) {
  if (!graph) {
    return;
  }
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const z = node.z ?? 0;
  const distance = 92;
  const length = Math.hypot(x, y, z) || 1;
  const ratio = 1 + distance / length;
  graph.cameraPosition({ x: x * ratio, y: y * ratio, z: z * ratio }, { x, y, z }, 650);
}

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return undefined;
    }
    const updateSize = () => {
      setSize({ width: element.clientWidth, height: element.clientHeight });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, size] as const;
}

function useWebGlAvailability() {
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    setSupported(isWebGlSupported());
  }, []);

  return supported;
}

function isWebGlSupported() {
  if (typeof window === "undefined" || typeof document === "undefined" || typeof WebGLRenderingContext === "undefined") {
    return false;
  }
  const canvas = document.createElement("canvas");
  return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
}

function useGraphTheme() {
  const [background, setBackground] = useState("#101114");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const styles = window.getComputedStyle(document.documentElement);
    const panel = styles.getPropertyValue("--panel").trim();
    setBackground(panel === "#232326" ? "#151519" : "#101114");
  }, []);

  return { background };
}
