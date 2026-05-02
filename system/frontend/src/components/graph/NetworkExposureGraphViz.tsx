import { AlertTriangle, Box, ExternalLink, FileKey, KeyRound, Network, RotateCcw, Router, Server, ShieldAlert, ZoomIn, ZoomOut } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { CSSProperties, MouseEvent, ReactNode } from "react";

import type { NetworkExposureGraph, NetworkExposureLinkKind, NetworkExposureNode, NetworkExposureNodeKind } from "../../domain/networkExposureGraph";
import { buildNetworkExposureDot, parseGraphNodeAppUrl } from "../../domain/networkExposureGraphDot";
import { relationLabel, riskTierLabel } from "../../domain/displayLabels";
import { formatDateTime, formatNumber } from "../../lib/format";
import { Button } from "../ui/button";

const NetworkExposureGraph3DView = lazy(() =>
  import("./NetworkExposureGraph3DView").then((module) => ({ default: module.NetworkExposureGraph3DView }))
);

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  target: "스캔 대상",
  endpoint: "엔드포인트",
  asset: "암호 자산",
  finding: "위험 발견"
};

const relationLabels: Record<NetworkExposureLinkKind, string> = {
  exposes: "스캔 대상이 엔드포인트를 노출합니다",
  presents: "엔드포인트가 인증서나 키를 제공합니다",
  supports: "엔드포인트가 프로토콜이나 알고리즘을 지원합니다",
  uses: "엔드포인트가 암호 자산을 사용합니다",
  has_finding: "자산에 위험 발견 항목이 있습니다"
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
          <span className="page-header__eyebrow">네트워크 노출 맵</span>
          <h2 id="network-graph-title">네트워크 암호 노출 현황</h2>
        </div>
        <div className="network-graph-header-actions">
          <div className="network-graph-view-toggle" role="group" aria-label="그래프 보기 방식">
            <Button type="button" size="sm" variant={viewMode === "2d" ? "primary" : "secondary"} onClick={() => setViewMode("2d")}>
              <Network size={14} />2D
            </Button>
            <Button type="button" size="sm" variant={viewMode === "3d" ? "primary" : "secondary"} onClick={() => setViewMode("3d")}>
              <Box size={14} />3D
            </Button>
          </div>
          {viewMode === "2d" ? (
            <div className="network-graph-zoom-controls" role="group" aria-label="2D 그래프 확대 축소">
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
          <div className="network-graph-stats" aria-label="네트워크 그래프 요약">
            <span>스캔 대상 {formatNumber(graph.stats.targets)}</span>
            <span>엔드포인트 {formatNumber(graph.stats.endpoints)}</span>
            <span>자산 {formatNumber(graph.stats.assets)}</span>
            <span>발견 항목 {formatNumber(graph.stats.findings)}</span>
          </div>
        </div>
      </div>

      <div className="network-graph-layout">
        {viewMode === "2d" ? (
          <div className="network-graph-stage network-graph-stage--svg" onClick={handleGraphClick}>
            {svg ? <div className="network-graph-svg" style={graphSvgStyle} dangerouslySetInnerHTML={{ __html: svg }} /> : null}
            {!hasGraph ? <GraphOverlay icon={<Network size={18} />} label="표시할 그래프 데이터가 없습니다" /> : null}
            {hasGraph && !svg && !renderError ? <GraphOverlay label="Graphviz 레이아웃 생성 중" /> : null}
            {isLoading ? <GraphOverlay label="네트워크 그래프 불러오는 중" /> : null}
            {error ? <GraphErrorOverlay label="그래프 데이터를 불러오지 못했습니다" onRetry={retry} /> : null}
            {!error && renderError ? <GraphErrorOverlay label="Graphviz 그래프를 렌더링하지 못했습니다" onRetry={retry} /> : null}
            {isFetching && !isLoading ? <span className="network-graph-refresh">동기화 중</span> : null}
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

        <aside className="network-graph-inspector" aria-label="선택한 그래프 노드">
          <div>
            <span className="network-graph-inspector__eyebrow">선택됨</span>
            <h3>{selectedNode?.label ?? "노드를 선택하세요"}</h3>
            {selectedNode ? <p>{nodeLabel(selectedNode)}</p> : <p>최근 관측 기준 {lastUpdated}</p>}
          </div>
          {selectedNode ? (
            <dl className="network-graph-meta">
              <div>
                <dt>노드 유형</dt>
                <dd>{kindLabels[selectedNode.kind]}</dd>
              </div>
              <div>
                <dt>위험 색상</dt>
                <dd>{selectedNode.riskTier ? riskTierLabel(selectedNode.riskTier) : "알 수 없음"}</dd>
              </div>
              <div>
                <dt>자산 수</dt>
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
    <div className="network-graph-legend" aria-label="그래프 노드 범례">
      <span><Server size={14} />스캔 대상</span>
      <span><Router size={14} />엔드포인트</span>
      <span><FileKey size={14} />인증서 자산</span>
      <span><KeyRound size={14} />키/알고리즘 자산</span>
      <span><ShieldAlert size={14} />위험 발견</span>
    </div>
  );
}

function RiskLegend() {
  return (
    <div className="network-graph-risk-legend" aria-label="그래프 위험 색상 범례">
      <span><i className="is-critical" />{riskTierLabel("CRITICAL")}</span>
      <span><i className="is-high" />{riskTierLabel("HIGH")}</span>
      <span><i className="is-medium" />{riskTierLabel("MEDIUM")}</span>
      <span><i className="is-low" />{riskTierLabel("LOW")}</span>
    </div>
  );
}

function RelationLegend() {
  return (
    <div className="network-graph-relations" aria-label="그래프 관계 범례">
      {(Object.entries(relationLabels) as Array<[NetworkExposureLinkKind, string]>).map(([kind, label]) => (
        <span key={kind} className={`is-${kind}`}>
          <i />
          <b>{relationLabel(kind)}</b>
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
  return [kindLabels[node.kind], node.subtitle, node.riskTier ? riskTierLabel(node.riskTier) : undefined].filter(Boolean).join(" · ");
}

function clampZoom(value: number) {
  const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  return Math.round(clamped * 100) / 100;
}
