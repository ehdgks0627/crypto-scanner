import type { RiskTier, Schema } from "../api/types";
import { assetTypeLabel, relationLabel, riskTierLabel } from "./displayLabels";

export type NetworkExposureNodeKind = "group" | "target" | "endpoint" | "asset" | "finding";
export type NetworkExposureLinkKind = "contains" | "exposes" | "presents" | "supports" | "uses" | "has_finding";

export type NetworkExposureNode = {
  id: string;
  kind: NetworkExposureNodeKind;
  label: string;
  subtitle?: string;
  color: string;
  val: number;
  riskTier?: RiskTier;
  refId?: number;
  assetCount: number;
};

export type NetworkExposureLink = {
  id: string;
  source: string;
  target: string;
  kind: NetworkExposureLinkKind;
  label: string;
  color: string;
  width: number;
};

export type NetworkExposureGraph = {
  nodes: NetworkExposureNode[];
  links: NetworkExposureLink[];
  stats: {
    groups: number;
    targets: number;
    endpoints: number;
    assets: number;
    findings: number;
    highestRiskTier?: RiskTier;
  };
};

const nodeColors: Record<NetworkExposureNodeKind, string> = {
  group: "#3f6f78",
  target: "#4b8ca8",
  endpoint: "#6d5a9a",
  asset: "#4f6f52",
  finding: "#c4413a"
};

const tierColors: Record<RiskTier, string> = {
  CRITICAL: "#c4413a",
  HIGH: "#d18a3a",
  MEDIUM: "#b9a23a",
  LOW: "#5d8a5a"
};

const linkColors: Record<NetworkExposureLinkKind, string> = {
  contains: "#3f6f78",
  exposes: "#4b8ca8",
  presents: "#6d5a9a",
  supports: "#5d8a5a",
  uses: "#8a8a8a",
  has_finding: "#c4413a"
};

const riskRank: Record<RiskTier, number> = {
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4
};

export function buildNetworkExposureGraph(
  assets: Schema<"AssetListItem">[],
  targets: Schema<"Target">[] = []
): NetworkExposureGraph {
  const nodes = new Map<string, NetworkExposureNode>();
  const links = new Map<string, NetworkExposureLink>();
  const targetsById = new Map(targets.map((target) => [target.id, target]));

  function addNode(node: Omit<NetworkExposureNode, "color" | "val" | "assetCount"> & Partial<Pick<NetworkExposureNode, "assetCount">>) {
    const existing = nodes.get(node.id);
    if (existing) {
      existing.assetCount += node.assetCount ?? 0;
      existing.riskTier = mostSevereTier(existing.riskTier, node.riskTier);
      return existing;
    }

    const created: NetworkExposureNode = {
      ...node,
      color: nodeColors[node.kind],
      val: 4,
      assetCount: node.assetCount ?? 0
    };
    nodes.set(created.id, created);
    return created;
  }

  function addLink(link: Omit<NetworkExposureLink, "color" | "width">) {
    if (links.has(link.id)) {
      return;
    }
    links.set(link.id, {
      ...link,
      color: linkColors[link.kind],
      width: link.kind === "has_finding" ? 2.2 : 1.7
    });
  }

  for (const asset of assets) {
    const target = asset.target_id ? targetsById.get(asset.target_id) : undefined;
    const group = groupFor(asset, target);
    const groupNodeId = `group:${group.key}`;
    const targetNodeId = targetNodeIdFor(asset, target);
    const endpointNodeId = endpointNodeIdFor(asset, target);
    const assetNodeId = `asset:${asset.id}`;
    const relation = relationForAsset(asset.asset_type);
    const tier = asset.risk?.tier;

    addNode({
      id: groupNodeId,
      kind: "group",
      label: group.label,
      subtitle: group.subtitle,
      riskTier: tier,
      assetCount: 1
    });
    addNode({
      id: targetNodeId,
      kind: "target",
      label: targetLabelFor(asset, target),
      subtitle: target?.ip ? `${target.ip}` : asset.target_label ?? undefined,
      riskTier: tier,
      refId: target?.id ?? asset.target_id ?? undefined,
      assetCount: 1
    });
    addNode({
      id: endpointNodeId,
      kind: "endpoint",
      label: endpointLabelFor(asset, target),
      subtitle: target ? `${target.transport} · ${target.protocol_hint}` : "observed endpoint",
      riskTier: tier,
      refId: target?.id ?? asset.target_id ?? undefined,
      assetCount: 1
    });
    addNode({
      id: assetNodeId,
      kind: "asset",
      label: asset.name,
      subtitle: assetSubtitle(asset),
      riskTier: tier,
      refId: asset.id,
      assetCount: 1
    });

    addLink({
      id: `contains:${groupNodeId}:${targetNodeId}`,
      source: groupNodeId,
      target: targetNodeId,
      kind: "contains",
      label: relationLabel("contains")
    });
    addLink({
      id: `exposes:${targetNodeId}:${endpointNodeId}`,
      source: targetNodeId,
      target: endpointNodeId,
      kind: "exposes",
      label: relationLabel("exposes")
    });
    addLink({
      id: `${relation}:${endpointNodeId}:${assetNodeId}`,
      source: endpointNodeId,
      target: assetNodeId,
      kind: relation,
      label: relationLabel(relation)
    });

    if (tier) {
      const findingNodeId = `finding:${tier}`;
      addNode({
        id: findingNodeId,
        kind: "finding",
        label: `${riskTierLabel(tier)} 위험`,
        subtitle: "위험 등급",
        riskTier: tier,
        assetCount: 1
      });
      addLink({
        id: `has_finding:${assetNodeId}:${findingNodeId}`,
        source: assetNodeId,
        target: findingNodeId,
        kind: "has_finding",
        label: relationLabel("has_finding")
      });
    }
  }

  const graphNodes = [...nodes.values()].map((node) => ({
    ...node,
    color: node.riskTier ? tierColors[node.riskTier] : nodeColors[node.kind],
    val: nodeValue(node)
  }));

  return {
    nodes: graphNodes,
    links: [...links.values()],
    stats: {
      groups: graphNodes.filter((node) => node.kind === "group").length,
      targets: graphNodes.filter((node) => node.kind === "target").length,
      endpoints: graphNodes.filter((node) => node.kind === "endpoint").length,
      assets: assets.length,
      findings: graphNodes.filter((node) => node.kind === "finding").reduce((sum, node) => sum + node.assetCount, 0),
      highestRiskTier: graphNodes.reduce<RiskTier | undefined>((highest, node) => mostSevereTier(highest, node.riskTier), undefined)
    }
  };
}

function groupFor(asset: Schema<"AssetListItem">, target?: Schema<"Target">) {
  if (target?.graph_group) {
    return {
      key: target.graph_group.key,
      label: target.graph_group.label,
      subtitle: target.graph_group.subtitle ?? undefined
    };
  }

  if (target?.agent_enabled) {
    return {
      key: `host:${target.host}`,
      label: target.display_name || target.host,
      subtitle: "Host Agent"
    };
  }

  if (target?.ip) {
    const range = ipv4Range24(target.ip);
    return {
      key: `target-scope:${range}`,
      label: range,
      subtitle: "IP 대역"
    };
  }

  if (target) {
    return {
      key: `target-scope:${target.host}`,
      label: target.host,
      subtitle: "스캔 대상 그룹"
    };
  }

  return {
    key: asset.target_label ? `target-label:${asset.target_label}` : "unmapped",
    label: asset.target_label ?? "매핑되지 않은 대상",
    subtitle: "대상 매핑 없음"
  };
}

function ipv4Range24(ip: string) {
  const match = ip.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.\d{1,3}$/);
  if (!match) {
    return ip;
  }
  return `${match[1]}.${match[2]}.${match[3]}.0/24`;
}

function targetNodeIdFor(asset: Schema<"AssetListItem">, target?: Schema<"Target">) {
  if (target) {
    return `target:${target.id}`;
  }
  if (asset.target_id) {
    return `target:${asset.target_id}`;
  }
  return asset.target_label ? `target-label:${asset.target_label}` : "target:unmapped";
}

function endpointNodeIdFor(asset: Schema<"AssetListItem">, target?: Schema<"Target">) {
  if (target) {
    return `endpoint:${target.id}:${target.transport}:${target.port}`;
  }
  return asset.target_label ? `endpoint:${asset.target_label}` : "endpoint:unmapped";
}

function targetLabelFor(asset: Schema<"AssetListItem">, target?: Schema<"Target">) {
  if (target) {
    return target.display_name || target.host;
  }
  return asset.target_label ?? "매핑되지 않은 대상";
}

function endpointLabelFor(asset: Schema<"AssetListItem">, target?: Schema<"Target">) {
  if (target) {
    return `${target.host}:${target.port}/${target.protocol_hint}`;
  }
  return asset.target_label ?? "매핑되지 않은 엔드포인트";
}

function assetSubtitle(asset: Schema<"AssetListItem">) {
  const algorithm = summaryString(asset.summary, "algorithm");
  const family = summaryString(asset.summary, "algorithm_family");
  return [assetTypeLabel(asset.asset_type), algorithm, family].filter(Boolean).join(" · ");
}

function summaryString(summary: Record<string, unknown>, key: string) {
  const value = summary[key];
  return typeof value === "string" && value ? value : undefined;
}

function relationForAsset(assetType: string): NetworkExposureLinkKind {
  if (assetType === "certificate" || assetType === "ssh_host_key" || assetType === "key") {
    return "presents";
  }
  if (assetType === "key_agreement" || assetType === "configuration" || assetType === "protocol" || assetType === "algorithm") {
    return "supports";
  }
  return "uses";
}

function mostSevereTier(left?: RiskTier, right?: RiskTier) {
  if (!left) {
    return right;
  }
  if (!right) {
    return left;
  }
  return riskRank[right] > riskRank[left] ? right : left;
}

function nodeValue(node: NetworkExposureNode) {
  const base = node.kind === "group" ? 12 : node.kind === "target" ? 10 : node.kind === "endpoint" ? 9 : node.kind === "finding" ? 8 : 6;
  const tierBoost = node.riskTier ? riskRank[node.riskTier] * 1.4 : 0;
  return Math.min(24, base + Math.sqrt(node.assetCount) + tierBoost);
}
