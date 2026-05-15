import type { DhsPriority, JobStatus, RiskTier } from "../../api/types";
import { riskTierLabels, statusLabels } from "../../domain/models";
import { statusLabel } from "../../domain/displayLabels";
import { Badge } from "../ui/badge";

export function RiskTierBadge({ tier }: { tier?: RiskTier | string | null }) {
  const normalized = (tier ?? "LOW") as RiskTier;
  const tone = normalized === "CRITICAL" ? "red" : normalized === "HIGH" ? "yellow" : normalized === "MEDIUM" ? "blue" : "green";
  return <Badge tone={tone}>{riskTierLabels[normalized] ?? tier}</Badge>;
}

export function DhsPriorityBadge({ priority }: { priority?: DhsPriority | string | null }) {
  if (!priority) {
    return <span>-</span>;
  }
  const tone = priority === "P1" ? "red" : priority === "P2" ? "yellow" : "green";
  return <Badge tone={tone}>{priority}</Badge>;
}

export function StatusBadge({ status }: { status?: JobStatus | string | null }) {
  const normalized = status ?? "PENDING";
  const tone =
    normalized === "COMPLETED" || normalized === "SUCCESS"
      ? "green"
      : normalized === "FAILED" || normalized === "ERROR" || normalized === "UNREACHABLE"
        ? "red"
        : normalized === "RUNNING" || normalized === "PARTIAL"
          ? "blue"
          : normalized === "CANCELLED"
            ? "yellow"
            : "neutral";
  return <Badge tone={tone}>{statusLabels[normalized as JobStatus] ?? statusLabel(normalized)}</Badge>;
}
