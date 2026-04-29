import type { JobStatus, RiskTier, Schema } from "../api/types";

export const riskTierOrder: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const riskTierLabels: Record<RiskTier, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low"
};

export const statusLabels: Record<JobStatus, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled"
};

export class JobProgressModel {
  constructor(private readonly progress: Schema<"JobProgress"> | null | undefined) {}

  percent(): number {
    const completed = Number(this.progress?.completed ?? 0);
    const total = Number(this.progress?.total ?? 0);
    if (!total) {
      return 0;
    }
    return Math.min(100, Math.round((completed / total) * 100));
  }

  label(): string {
    if (!this.progress) {
      return "대기 중";
    }
    const currentTarget = this.progress.current_target ? String(this.progress.current_target) : null;
    const currentScanner = this.progress.current_scanner ? String(this.progress.current_scanner) : null;
    if (currentTarget && currentScanner) {
      return `${currentTarget} · ${currentScanner}`;
    }
    if (currentTarget) {
      return currentTarget;
    }
    return `${this.progress.completed ?? 0}/${this.progress.total ?? 0}`;
  }
}

export class SnapshotSummaryModel {
  constructor(private readonly snapshot: Schema<"CbomSnapshot"> | Schema<"DashboardSnapshot"> | null | undefined) {}

  label(): string {
    if (!this.snapshot) {
      return "스냅샷 없음";
    }
    return `#${this.snapshot.id} · ${new Date(this.snapshot.created_at).toLocaleString("ko-KR")}`;
  }
}
