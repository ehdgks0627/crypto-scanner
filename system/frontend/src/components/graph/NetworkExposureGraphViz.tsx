import { AlertTriangle, Box, ExternalLink, FileKey, KeyRound, Network, RotateCcw, Router, Server, ShieldAlert, ZoomIn, ZoomOut } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { CSSProperties, MouseEvent, ReactNode } from "react";

import type { NetworkExposureGraph, NetworkExposureLinkKind, NetworkExposureNode, NetworkExposureNodeKind } from "../../domain/networkExposureGraph";
import { buildNetworkExposureDot, parseGraphNodeAppUrl } from "../../domain/networkExposureGraphDot";
import { formatDateTime, formatNumber } from "../../lib/format";
import { Button } from "../ui/button";

const NetworkExposureGraph3DView = lazy(() =>
  import("./NetworkExposureGraph3DView").then((module) => ({ default: module.NetworkExposureGraph3DView }))
);

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  target: "Target",
  endpoint: "Endpoint",
  asset: "Crypto Asset",
  finding: "Finding"
};

const relationLabels: Record<NetworkExposureLinkKind, string> = {
  exposes: "Target exposes an endpoint",
  presents: "Endpoint presents crypto material",
  supports: "Endpoint supports a protocol/algorithm",
  uses: "Endpoint uses a crypto asset",
  has_finding: "Asset has a risk finding"
};

type GraphViewMode = "2d" | "3d";

const MIN_ZOOM = 0.7;
const MAX_ZOOM = 1.6;
const ZOOM_STEP = 0.15;

export function NetworkExposureGraphViz({
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
  const [viewMode, setViewMode] = useState<GraphViewMode>("2d");
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  const [zoom, setZoom] = useState(1);
  const [svg, setSvg] = useState("");
  const [renderError, setRenderError] = useState<unknown>();
  const [renderRevision, setRenderRevision] = useState(0);
  const dot = useMemo(() => buildNetworkExposureDot(graph), [graph]);
  const nodeById = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : undefined;
  const lastUpdated = updatedAt ? formatDateTime(new Date(updatedAt).toISOString()) : "-";
  const hasGraph = graph.nodes.length > 0;

  useEffect(() => {
    let cancelled = false;
    setSvg("");
    setRenderError(undefined);

    if (!hasGraph) {
      return undefined;
    }

    import("@hpcc-js/wasm/graphviz")
      .then(({ Graphviz }) => Graphviz.load())
      .then((graphviz) => graphviz.sfdp(dot, "svg"))
      .then((nextSvg) => {
        if (!cancelled) {
          setSvg(nextSvg);
        }
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          setRenderError(nextError);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [dot, hasGraph, renderRevision]);

  useEffect(() => {
    if (selectedNodeId && !nodeById.has(selectedNodeId)) {
      setSelectedNodeId(undefined);
    }
  }, [nodeById, selectedNodeId]);

  function handleGraphClick(event: MouseEvent<HTMLDivElement>) {
    const element = event.target instanceof Element ? event.target : undefined;
    const anchor = element?.closest("a");
    const href = anchor?.getAttribute("xlink:href") ?? anchor?.getAttribute("href");
    const nodeId = parseGraphNodeAppUrl(href);
    if (!nodeId) {
      return;
    }
    event.preventDefault();
    if (nodeById.has(nodeId)) {
      setSelectedNodeId(nodeId);
    }
  }

  function retry() {
    setRenderRevision((current) => current + 1);
    onRetry?.();
  }

  function zoomBy(delta: number) {
    setZoom((current) => clampZoom(current + delta));
  }

  const graphSvgStyle = {
    width: `${Math.round(zoom * 100)}%`,
    minWidth: `${Math.round(920 * zoom)}px`
  } satisfies CSSProperties;

  return (
    <section className="network-graph-band" aria-labelledby="network-graph-title">
      <div className="network-graph-band__header">
        <div>
          <span className="page-header__eyebrow">NETWORK EXPOSURE MAP</span>
          <h2 id="network-graph-title">네트워크 암호 노출 현황</h2>
        </div>
        <div className="network-graph-header-actions">
          <div className="network-graph-view-toggle" role="group" aria-label="Graph view mode">
            <Button type="button" size="sm" variant={viewMode === "2d" ? "primary" : "secondary"} onClick={() => setViewMode("2d")}>
              <Network size={14} />2D
            </Button>
            <Button type="button" size="sm" variant={viewMode === "3d" ? "primary" : "secondary"} onClick={() => setViewMode("3d")}>
              <Box size={14} />3D
            </Button>
          </div>
          {viewMode === "2d" ? (
            <div className="network-graph-zoom-controls" role="group" aria-label="2D graph zoom controls">
              <Button type="button" size="icon" variant="ghost" aria-label="2D 그래프 축소" disabled={zoom <= MIN_ZOOM} onClick={() => zoomBy(-ZOOM_STEP)}>
                <ZoomOut size={15} />
              </Button>
              <span>{Math.round(zoom * 100)}%</span>
              <Button type="button" size="icon" variant="ghost" aria-label="2D 그래프 확대" disabled={zoom >= MAX_ZOOM} onClick={() => zoomBy(ZOOM_STEP)}>
                <ZoomIn size={15} />
              </Button>
              <Button type="button" size="icon" variant="ghost" aria-label="2D 그래프 줌 초기화" onClick={() => setZoom(1)}>
                <RotateCcw size={15} />
              </Button>
            </div>
          ) : null}
          <div className="network-graph-stats" aria-label="Network graph summary">
            <span>Targets {formatNumber(graph.stats.targets)}</span>
            <span>Endpoints {formatNumber(graph.stats.endpoints)}</span>
            <span>Assets {formatNumber(graph.stats.assets)}</span>
            <span>Findings {formatNumber(graph.stats.findings)}</span>
          </div>
        </div>
      </div>

      <div className="network-graph-layout">
        {viewMode === "2d" ? (
          <div className="network-graph-stage network-graph-stage--svg" onClick={handleGraphClick}>
            {svg ? <div className="network-graph-svg" style={graphSvgStyle} dangerouslySetInnerHTML={{ __html: svg }} /> : null}
            {!hasGraph ? <GraphOverlay icon={<Network size={18} />} label="표시할 그래프 데이터가 없습니다" /> : null}
            {hasGraph && !svg && !renderError ? <GraphOverlay label="Graphviz layout 생성 중" /> : null}
            {isLoading ? <GraphOverlay label="네트워크 그래프 불러오는 중" /> : null}
            {error ? <GraphErrorOverlay label="그래프 데이터를 불러오지 못했습니다" onRetry={retry} /> : null}
            {!error && renderError ? <GraphErrorOverlay label="Graphviz 그래프를 렌더링하지 못했습니다" onRetry={retry} /> : null}
            {isFetching && !isLoading ? <span className="network-graph-refresh">syncing</span> : null}
          </div>
        ) : (
          <Suspense fallback={<GraphStageFallback label="3D 그래프 준비 중" />}>
            <NetworkExposureGraph3DView
              graph={graph}
              isLoading={isLoading}
              isFetching={isFetching}
              error={error}
              selectedNodeId={selectedNodeId}
              onRetry={onRetry}
              onSelectNode={setSelectedNodeId}
            />
          </Suspense>
        )}

        <aside className="network-graph-inspector" aria-label="Selected graph node">
          <div>
            <span className="network-graph-inspector__eyebrow">Selected</span>
            <h3>{selectedNode?.label ?? "노드를 선택하세요"}</h3>
            {selectedNode ? <p>{nodeLabel(selectedNode)}</p> : <p>최근 관측 기준 {lastUpdated}</p>}
          </div>
          {selectedNode ? (
            <dl className="network-graph-meta">
              <div>
                <dt>Shape</dt>
                <dd>{kindLabels[selectedNode.kind]}</dd>
              </div>
              <div>
                <dt>Risk Color</dt>
                <dd>{selectedNode.riskTier ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt>Assets</dt>
                <dd>{formatNumber(selectedNode.assetCount)}</dd>
              </div>
            </dl>
          ) : (
            <>
              <GraphLegend />
              <RiskLegend />
              <RelationLegend />
            </>
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
    <div className="network-graph-legend" aria-label="Graph node legend">
      <span><Server size={14} />Target node</span>
      <span><Router size={14} />Endpoint node</span>
      <span><FileKey size={14} />Certificate asset</span>
      <span><KeyRound size={14} />Key/algorithm asset</span>
      <span><ShieldAlert size={14} />Risk finding</span>
    </div>
  );
}

function RiskLegend() {
  return (
    <div className="network-graph-risk-legend" aria-label="Graph risk color legend">
      <span><i className="is-critical" />CRITICAL</span>
      <span><i className="is-high" />HIGH</span>
      <span><i className="is-medium" />MEDIUM</span>
      <span><i className="is-low" />LOW</span>
    </div>
  );
}

function RelationLegend() {
  return (
    <div className="network-graph-relations" aria-label="Graph relation legend">
      {(Object.entries(relationLabels) as Array<[NetworkExposureLinkKind, string]>).map(([kind, label]) => (
        <span key={kind} className={`is-${kind}`}>
          <i />
          <b>{kind.replace("_", " ")}</b>
          {label}
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

function GraphStageFallback({ label }: { label: string }) {
  return (
    <div className="network-graph-stage network-graph-stage--3d">
      <GraphOverlay label={label} />
    </div>
  );
}

function GraphErrorOverlay({ label, onRetry }: { label: string; onRetry?: () => void }) {
  return (
    <div className="network-graph-overlay network-graph-overlay--error" role="alert">
      <AlertTriangle size={18} />
      <span>{label}</span>
      {onRetry ? (
        <Button type="button" size="sm" onClick={onRetry}>
          재시도
        </Button>
      ) : null}
    </div>
  );
}

function nodeLabel(node: NetworkExposureNode) {
  return [kindLabels[node.kind], node.subtitle, node.riskTier].filter(Boolean).join(" · ");
}

function clampZoom(value: number) {
  const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  return Math.round(clamped * 100) / 100;
}
