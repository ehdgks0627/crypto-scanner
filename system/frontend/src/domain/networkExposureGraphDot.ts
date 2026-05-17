import type { RiskTier } from "../api/types";
import { relationLabel, riskTierLabel } from "./displayLabels";
import type { NetworkExposureGraph, NetworkExposureLink, NetworkExposureLinkKind, NetworkExposureNode, NetworkExposureNodeKind } from "./networkExposureGraph";

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  group: "수집 그룹",
  target: "스캔 대상",
  endpoint: "엔드포인트",
  asset: "암호 자산",
  finding: "위험 발견"
};

const kindShapes: Record<NetworkExposureNodeKind, string> = {
  group: "folder",
  target: "box3d",
  endpoint: "component",
  asset: "note",
  finding: "octagon"
};

const riskStyles: Record<RiskTier | "UNKNOWN", { border: string; fill: string; text: string }> = {
  CRITICAL: { border: "#c4413a", fill: "#f9e6e4", text: "#6f1f1a" },
  HIGH: { border: "#d18a3a", fill: "#fbefd9", text: "#754713" },
  MEDIUM: { border: "#b9a23a", fill: "#f6f0cf", text: "#5d5119" },
  LOW: { border: "#5d8a5a", fill: "#e6f1e4", text: "#2e542c" },
  UNKNOWN: { border: "#9a9a9a", fill: "#f4f4f4", text: "#1a1a1a" }
};

const edgeStyles: Record<NetworkExposureLinkKind, { color: string; label: string; style: string }> = {
  contains: { color: "#3f6f78", label: relationLabel("contains"), style: "solid" },
  exposes: { color: "#4b8ca8", label: relationLabel("exposes"), style: "solid" },
  presents: { color: "#6d5a9a", label: relationLabel("presents"), style: "solid" },
  supports: { color: "#5d8a5a", label: relationLabel("supports"), style: "solid" },
  uses: { color: "#8a8a8a", label: relationLabel("uses"), style: "solid" },
  has_finding: { color: "#c4413a", label: relationLabel("has_finding"), style: "dashed" }
};

export function buildNetworkExposureDot(graph: NetworkExposureGraph) {
  const lines = [
    "graph NetworkExposure {",
    '  graph [layout=sfdp, bgcolor="transparent", pad="0.24", overlap=prism, overlap_scaling=-5, sep="+24", K=0.95, repulsiveforce=1.55, start=37, splines=true, outputorder=edgesfirst];',
    '  node [fontname="Inter", fontsize=11, margin="0.13,0.08"];',
    '  edge [fontname="JetBrains Mono", fontsize=9, penwidth=1.55, len=1.6];',
    ...graph.nodes.map(nodeStatement),
    ...graph.links.map(edgeStatement),
    "}"
  ];
  return lines.join("\n");
}

export function graphNodeAppUrl(nodeId: string) {
  return `#graph-node:${encodeURIComponent(nodeId)}`;
}

export function parseGraphNodeAppUrl(href: string | null | undefined) {
  const prefix = "#graph-node:";
  if (!href?.startsWith(prefix)) {
    return undefined;
  }
  try {
    return decodeURIComponent(href.slice(prefix.length));
  } catch {
    return undefined;
  }
}

function nodeStatement(node: NetworkExposureNode) {
  const risk = riskStyles[node.riskTier ?? "UNKNOWN"];
  const label = dotEscape(nodeLabel(node));
  const tooltip = dotEscape([kindLabels[node.kind], node.label, node.subtitle].filter(Boolean).join(" | "));
  return [
    `  ${quoteId(node.id)} [`,
    `    label="${label}",`,
    `    shape=${kindShapes[node.kind]},`,
    '    style="filled",',
    `    color="${risk.border}",`,
    `    fillcolor="${risk.fill}",`,
    `    fontcolor="${risk.text}",`,
    '    penwidth=1.8,',
    `    tooltip="${tooltip}",`,
    `    URL="${graphNodeAppUrl(node.id)}",`,
    '    target="_self"',
    "  ];"
  ].join("\n");
}

function edgeStatement(link: NetworkExposureLink) {
  const style = edgeStyles[link.kind];
  return [
    `  ${quoteId(link.source)} -- ${quoteId(link.target)} [`,
    `    label="${dotEscape(style.label)}",`,
    `    color="${style.color}",`,
    `    fontcolor="${style.color}",`,
    `    style="${style.style}",`,
    `    tooltip="${dotEscape(style.label)}"`,
    "  ];"
  ].join("\n");
}

function nodeLabel(node: NetworkExposureNode) {
  const meta = node.kind === "finding" ? `${node.assetCount}개 자산` : node.assetCount > 1 ? `${node.assetCount}개 자산` : undefined;
  return [
    ...wrapText(node.label, 24, 2),
    ...wrapText(node.subtitle ?? "", 26, 1),
    node.riskTier ? `${kindLabels[node.kind]} · ${riskTierLabel(node.riskTier)}` : kindLabels[node.kind],
    meta
  ]
    .filter(Boolean)
    .join("\n");
}

function wrapText(value: string, lineLength: number, maxLines: number) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return [];
  }
  const words = normalized.split(" ");
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= lineLength) {
      current = next;
      continue;
    }
    if (current) {
      lines.push(current);
    }
    current = word.length > lineLength ? `${word.slice(0, lineLength - 3)}...` : word;
    if (lines.length === maxLines) {
      break;
    }
  }

  if (current && lines.length < maxLines) {
    lines.push(current);
  }

  if (lines.length > 0 && words.join(" ").length > lines.join(" ").length) {
    lines[lines.length - 1] = truncate(lines[lines.length - 1], lineLength);
  }

  return lines;
}

function truncate(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
}

function quoteId(id: string) {
  return `"${dotEscape(id)}"`;
}

function dotEscape(value: string) {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")
    .replace(/\r/g, "");
}
