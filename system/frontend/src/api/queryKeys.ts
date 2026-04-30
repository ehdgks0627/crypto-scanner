export const queryKeys = {
  dashboard: {
    all: ["dashboard"] as const,
    summary: (snapshotId?: number) => ["dashboard", "summary", snapshotId] as const
  },
  targets: {
    all: ["targets"] as const,
    list: (filters?: unknown) => ["targets", "list", filters] as const,
    detail: (id: number) => ["targets", "detail", id] as const
  },
  discoveries: {
    all: ["discoveries"] as const,
    list: (status?: string) => ["discoveries", "list", status] as const,
    detail: (id: number) => ["discoveries", "detail", id] as const,
    endpoints: (id: number) => ["discoveries", "endpoints", id] as const
  },
  jobs: {
    all: ["jobs"] as const,
    list: (status?: string) => ["jobs", "list", status] as const,
    detail: (id: number) => ["jobs", "detail", id] as const,
    logs: (id: number) => ["jobs", "logs", id] as const
  },
  snapshots: {
    all: ["snapshots"] as const,
    detail: (id: number) => ["snapshots", "detail", id] as const,
    export: (id: number) => ["snapshots", "export", id] as const,
    diff: (id: number, other?: number) => ["snapshots", "diff", id, other] as const,
    assetsPrefix: (id: number) => ["snapshots", "assets", id] as const,
    assets: (id: number, filters?: unknown) => ["snapshots", "assets", id, filters] as const
  },
  assets: {
    all: ["assets"] as const,
    detail: (id: number) => ["assets", "detail", id] as const
  },
  risk: {
    all: ["risk"] as const,
    weights: ["risk", "weights"] as const,
    listPrefix: (snapshotId: number) => ["risk", "list", snapshotId] as const,
    list: (snapshotId: number, filters?: unknown) => ["risk", "list", snapshotId, filters] as const,
    top: (snapshotId: number) => ["risk", "top", snapshotId] as const
  },
  migration: {
    all: ["migration"] as const,
    planPrefix: (snapshotId: number) => ["migration", "plan", snapshotId] as const,
    plan: (snapshotId: number, filters?: unknown) => ["migration", "plan", snapshotId, filters] as const,
    impact: (snapshotId: number, assetIds: number[]) => ["migration", "impact", snapshotId, assetIds] as const
  },
  performance: {
    all: ["performance"] as const,
    runsPrefix: (snapshotId: number) => ["performance", "runs", snapshotId] as const,
    runs: (snapshotId: number, filters?: unknown) => ["performance", "runs", snapshotId, filters] as const,
    detail: (snapshotId: number, runId: number) => ["performance", "detail", snapshotId, runId] as const,
    history: (assetId: number) => ["performance", "history", assetId] as const
  },
  agents: {
    all: ["agents"] as const,
    listPrefix: ["agents", "list"] as const,
    list: (active?: boolean) => ["agents", "list", active] as const,
    detail: (id: string) => ["agents", "detail", id] as const
  },
  meta: {
    protocols: ["meta", "protocols"] as const,
    scanners: ["meta", "scanners"] as const,
    algorithmRiskTable: ["meta", "algorithm-risk-table"] as const
  },
  health: ["health"] as const
};
