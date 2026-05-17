import type { RiskTier } from "../api/types";
import { relationLabel, riskTierLabel } from "./displayLabels";
import type { NetworkExposureGraph, NetworkExposureLink, NetworkExposureLinkKind, NetworkExposureNode, NetworkExposureNodeKind } from "./networkExposureGraph";

const kindLabels: Record<NetworkExposureNodeKind, string> = {
  group: "수집 영역",
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
  const clusters = buildGroupClusters(graph);
  const clusteredNodeIds = new Set(clusters.flatMap((cluster) => cluster.members.map((node) => node.id)));
  const clusteredGroupIds = new Set(clusters.map((cluster) => cluster.group.id));
  const standaloneNodes = graph.nodes.filter((node) => !clusteredNodeIds.has(node.id) && !clusteredGroupIds.has(node.id));
  const visibleLinks = graph.links.filter((link) => link.kind !== "contains" && !clusteredGroupIds.has(link.source) && !clusteredGroupIds.has(link.target));
  const lines = [
    "digraph NetworkExposure {",
    '  graph [layout=dot, bgcolor="transparent", pad="0.12", rankdir=LR, compound=true, newrank=true, nodesep="0.22", ranksep="0.48", splines=ortho, outputorder=edgesfirst];',
    '  node [fontname="Inter", fontsize=10, margin="0.1,0.06"];',
    '  edge [fontname="JetBrains Mono", fontsize=8, penwidth=1.4, arrowsize=0.6];',
    ...clusters.map(clusterStatement),
    ...standaloneNodes.map((node) => nodeStatement(node)),
    ...visibleLinks.map(edgeStatement),
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

function nodeStatement(node: NetworkExposureNode, options: { compact?: boolean } = {}) {
  const compact = options.compact ?? false;
  const risk = riskStyles[node.riskTier ?? "UNKNOWN"];
  const label = dotEscape(compact ? compactNodeLabel(node) : nodeLabel(node));
  const tooltip = dotEscape([kindLabels[node.kind], node.label, node.subtitle].filter(Boolean).join(" | "));
  return [
    `  ${quoteId(node.id)} [`,
    `    label="${label}",`,
    `    shape=${compact && node.kind === "target" ? "box" : kindShapes[node.kind]},`,
    '    style="filled",',
    `    color="${risk.border}",`,
    `    fillcolor="${risk.fill}",`,
    `    fontcolor="${risk.text}",`,
    `    fontsize=${compact ? 9 : 10},`,
    `    margin="${compact ? "0.06,0.035" : "0.1,0.06"}",`,
    `    penwidth=${compact ? 1.25 : 1.8},`,
    `    tooltip="${tooltip}",`,
    `    URL="${graphNodeAppUrl(node.id)}",`,
    '    target="_self"',
    "  ];"
  ].join("\n");
}

function edgeStatement(link: NetworkExposureLink) {
  const style = edgeStyles[link.kind];
  return [
    `  ${quoteId(link.source)} -> ${quoteId(link.target)} [`,
    `    label="${dotEscape(style.label)}",`,
    `    color="${style.color}",`,
    `    fontcolor="${style.color}",`,
    `    style="${style.style}",`,
    '    arrowhead="vee",',
    `    tooltip="${dotEscape(style.label)}"`,
    "  ];"
  ].join("\n");
}

type GraphCluster = {
  id: string;
  group: NetworkExposureNode;
  memberIds: Set<string>;
  members: NetworkExposureNode[];
};

function buildGroupClusters(graph: NetworkExposureGraph) {
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const clusteredNodeIds = new Set<string>();
  const clusters: GraphCluster[] = [];

  for (const link of graph.links) {
    if (link.kind !== "contains") {
      continue;
    }

    const group = nodesById.get(link.source);
    if (group?.kind !== "group") {
      continue;
    }

    const target = nodesById.get(link.target);
    if (target?.kind !== "target" || clusteredNodeIds.has(target.id)) {
      continue;
    }

    const memberIds = new Set([target.id]);
    if (memberIds.size === 0) {
      continue;
    }

    for (const memberId of memberIds) {
      clusteredNodeIds.add(memberId);
    }

    clusters.push({
      id: `cluster_${clusterIdSuffix(group.id)}`,
      group,
      memberIds,
      members: [...memberIds].map((memberId) => nodesById.get(memberId)).filter((node): node is NetworkExposureNode => Boolean(node))
    });
  }

  return clusters;
}

function clusterStatement(cluster: GraphCluster) {
  const risk = riskStyles[cluster.group.riskTier ?? "UNKNOWN"];
  const label = clusterLabel(cluster.group);
  const tooltip = [kindLabels.group, cluster.group.label, cluster.group.subtitle].filter(Boolean).join(" | ");
  return [
    `  subgraph ${quoteId(cluster.id)} {`,
    `    label="${dotEscape(label)}";`,
    `    tooltip="${dotEscape(tooltip)}";`,
    `    URL="${graphNodeAppUrl(cluster.group.id)}";`,
    '    target="_self";',
    '    labelloc="t";',
    '    labeljust="l";',
    '    style="rounded,filled";',
    `    color="${risk.border}";`,
    `    fillcolor="${clusterFillColor(risk.fill)}";`,
    `    fontcolor="${risk.text}";`,
    '    fontsize=9;',
    '    penwidth=1.2;',
    '    margin=3;',
    ...cluster.members.map((node) => indent(nodeStatement(node, { compact: true }), 4)),
    "  }"
  ].join("\n");
}

function clusterLabel(group: NetworkExposureNode) {
  return truncate(group.label, 26);
}

function clusterIdSuffix(value: string) {
  return value.replace(/[^a-zA-Z0-9_]/g, "_").replace(/^_+/, "") || "group";
}

function clusterFillColor(fill: string) {
  return fill;
}

function indent(value: string, spaces: number) {
  const prefix = " ".repeat(spaces);
  return value
    .split("\n")
    .map((line) => `${prefix}${line}`)
    .join("\n");
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

function compactNodeLabel(node: NetworkExposureNode) {
  return truncate(node.label, 18);
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
