import { AlertTriangle, Network } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ForceGraphMethods } from "react-force-graph-3d";
import * as THREE from "three";

import type { NetworkExposureGraph, NetworkExposureLink, NetworkExposureNode, NetworkExposureNodeKind } from "../../domain/networkExposureGraph";
import { Button } from "../ui/button";

const ForceGraph3D = lazy(() => import("react-force-graph-3d"));

const graphRendererConfig = { preserveDrawingBuffer: true, antialias: true } as const;

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  target: "Target",
  endpoint: "Endpoint",
  asset: "Crypto Asset",
  finding: "Finding"
};

type RenderNode = NetworkExposureNode & {
  x?: number;
  y?: number;
  z?: number;
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
  onSelectNode: (nodeId: string) => void;
}) {
  const graphRef = useRef<ForceGraphMethods>();
  const [stageRef, size] = useElementSize<HTMLDivElement>();
  const canUseWebGl = useWebGlAvailability();
  const background = useGraphBackground();
  const hasGraph = graph.nodes.length > 0;
  const graphData = useMemo(() => ({ nodes: graph.nodes, links: graph.links }), [graph.links, graph.nodes]);

  return (
    <div className="network-graph-stage network-graph-stage--3d" ref={stageRef}>
      {hasGraph && canUseWebGl ? (
        <Suspense fallback={<GraphOverlay label="3D 그래프 준비 중" />}>
          <ForceGraph3D
            ref={graphRef}
            graphData={graphData}
            width={Math.max(size.width, 320)}
            height={Math.max(size.height, 360)}
            backgroundColor={background}
            rendererConfig={graphRendererConfig}
            showNavInfo={false}
            nodeId="id"
            nodeRelSize={5}
            nodeVal={(node: unknown) => (node as NetworkExposureNode).val}
            nodeColor={(node: unknown) => (node as NetworkExposureNode).color}
            nodeLabel={(node: unknown) => nodeLabel(node as NetworkExposureNode)}
            nodeThreeObject={(node: unknown) => createNodeObject(node as NetworkExposureNode, (node as NetworkExposureNode).id === selectedNodeId)}
            linkLabel={(link: unknown) => linkLabel(link as NetworkExposureLink)}
            linkColor={(link: unknown) => (link as NetworkExposureLink).color}
            linkWidth={(link: unknown) => (link as NetworkExposureLink).width}
            linkOpacity={0.72}
            linkDirectionalArrowLength={4.5}
            linkDirectionalArrowRelPos={0.84}
            linkDirectionalParticles={(link: unknown) => ((link as NetworkExposureLink).kind === "exposes" ? 3 : 1)}
            linkDirectionalParticleSpeed={0.004}
            linkDirectionalParticleWidth={2}
            cooldownTicks={140}
            d3VelocityDecay={0.32}
            dagMode="radialout"
            dagLevelDistance={115}
            enableNodeDrag
            onEngineStop={() => graphRef.current?.zoomToFit(500, 28)}
            onNodeClick={(node) => {
              const selected = node as RenderNode;
              onSelectNode(selected.id);
              focusNode(graphRef.current, selected);
            }}
          />
        </Suspense>
      ) : null}

      {!hasGraph ? <GraphOverlay icon={<Network size={18} />} label="표시할 그래프 데이터가 없습니다" /> : null}
      {hasGraph && !canUseWebGl ? <GraphOverlay label="이 브라우저에서는 3D WebGL 그래프를 사용할 수 없습니다" /> : null}
      {isLoading ? <GraphOverlay label="네트워크 그래프 불러오는 중" /> : null}
      {error ? <GraphErrorOverlay onRetry={onRetry} /> : null}
      {isFetching && !isLoading ? <span className="network-graph-refresh">syncing</span> : null}
    </div>
  );
}

function createNodeObject(node: NetworkExposureNode, selected: boolean) {
  const group = new THREE.Group();
  const size = Math.max(5, Math.min(15, node.val * 0.9));
  const geometry = geometryForNode(node.kind, size);
  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshLambertMaterial({
      color: node.color,
      emissive: selected ? new THREE.Color(node.color) : new THREE.Color("#000000"),
      emissiveIntensity: selected ? 0.35 : 0,
      transparent: true,
      opacity: selected ? 1 : 0.9
    })
  );
  group.add(mesh);
  group.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({ color: selected ? "#ffffff" : "#1a1a1a", transparent: true, opacity: selected ? 0.9 : 0.42 })));

  const label = createTextSprite(node.label, node.riskTier ?? kindLabels[node.kind], selected);
  label.position.y = size + 8;
  group.add(label);
  return group;
}

function geometryForNode(kind: NetworkExposureNodeKind, size: number) {
  if (kind === "target") {
    return new THREE.BoxGeometry(size * 1.45, size * 0.86, size * 0.86);
  }
  if (kind === "endpoint") {
    return new THREE.CylinderGeometry(size * 0.62, size * 0.62, size * 1.15, 18);
  }
  if (kind === "finding") {
    return new THREE.OctahedronGeometry(size * 0.92);
  }
  return new THREE.IcosahedronGeometry(size * 0.82, 0);
}

function createTextSprite(label: string, meta: string, selected: boolean) {
  const canvas = document.createElement("canvas");
  canvas.width = 384;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = selected ? "rgba(255,255,255,0.96)" : "rgba(255,255,255,0.86)";
    context.strokeStyle = selected ? "rgba(15,15,15,0.72)" : "rgba(15,15,15,0.42)";
    context.lineWidth = selected ? 5 : 3;
    roundRect(context, 12, 18, 360, 88, 8);
    context.fill();
    context.stroke();
    context.fillStyle = "#141414";
    context.font = "700 22px Inter, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(truncate(label, 28), 192, 50);
    context.fillStyle = "#555555";
    context.font = "600 16px Inter, sans-serif";
    context.fillText(truncate(meta, 24), 192, 78);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }));
  sprite.scale.set(42, 14, 1);
  return sprite;
}

function roundRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function nodeLabel(node: NetworkExposureNode) {
  return [kindLabels[node.kind], node.label, node.subtitle, node.riskTier].filter(Boolean).join(" · ");
}

function linkLabel(link: NetworkExposureLink) {
  return link.label.replace("_", " ");
}

function focusNode(graph: ForceGraphMethods | undefined, node: RenderNode) {
  if (!graph) {
    return;
  }
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const z = node.z ?? 0;
  const distance = 120;
  const length = Math.hypot(x, y, z) || 1;
  const ratio = 1 + distance / length;
  graph.cameraPosition({ x: x * ratio, y: y * ratio, z: z * ratio }, { x, y, z }, 650);
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

function useGraphBackground() {
  const [background, setBackground] = useState("#101114");

  useEffect(() => {
    const styles = window.getComputedStyle(document.documentElement);
    const panel = styles.getPropertyValue("--panel").trim();
    setBackground(panel || "#101114");
  }, []);

  return background;
}

function truncate(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
}
