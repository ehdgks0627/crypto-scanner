export type DemoStepStatus = "completed" | "ready" | "locked";

export type DemoStep = {
  id: "targets" | "agents" | "cbom" | "risk" | "migration" | "verification";
  index: number;
  title: string;
  subtitle: string;
  status: DemoStepStatus;
  progress: number;
};

export type DemoTarget = {
  id: string;
  value: string;
  kind: string;
  service: string;
};

export type DemoHostLabel = {
  host: string;
  description: string;
  role: string;
  data_classes: string[];
  partners: string[];
  retention: string;
};

export type DemoAsset = {
  id: string;
  host: string;
  domain: string;
  name: string;
  asset_type: string;
  algorithm_group: string;
  algorithm: string;
  key_size: number | null;
  expires: string;
  role: string;
  neighbors: string[];
  data_tags: string[];
  retention: string;
  discovered_by: string[];
  priority: "P1" | "P2" | "P3";
  risk_score: number;
  dormant: boolean;
  quantum_vulnerable: boolean;
};

export type DemoAgentRun = {
  status: "pending" | "completed";
  progress: number;
  total_assets: number;
  discovery_assets: number;
  host_assets: number;
  overlap_assets: number;
  active_keys: number;
  dormant_keys: number;
  algorithm_distribution: Array<{
    label: string;
    count: number;
    quantum_vulnerable: boolean;
  }>;
  logs: {
    discovery: string[];
    host: string[];
  };
};

export type DemoRisk = {
  status: "pending" | "completed";
  summary: Record<"P1" | "P2" | "P3", number>;
  example: null | {
    asset_id: string;
    score: number;
    priority: "P1";
    criteria: Record<string, { level: "HIGH" | "MED" | "LOW"; reason: string }>;
  };
};

export type DemoMigration = {
  status: "pending" | "completed";
  recommendation_count: number;
  items: Array<{
    asset_id: string;
    current_algorithm: string;
    recommended_algorithm: string;
    priority: "P1" | "P2" | "P3";
    reason: string;
  }>;
};

export type DemoVerification = {
  status: "pending" | "completed";
  overall_status?: "PASS" | "WARN" | "FAIL";
  handshake_success_rate?: number;
  latency_before_ms?: number;
  latency_after_ms?: number;
  throughput_before_rps?: number;
  throughput_after_rps?: number;
  compatibility_before?: number;
  compatibility_after?: number;
  failure_count?: number;
  cbom_changes?: number;
  checks?: Array<{ name: string; status: "PASS" | "WARN" | "FAIL"; value: string }>;
};

export type DemoSession = {
  scenario: string;
  current_step: number;
  current_step_id: DemoStep["id"];
  is_complete: boolean;
  steps: DemoStep[];
  targets: DemoTarget[];
  host_labels: DemoHostLabel[];
  agent_run: DemoAgentRun;
  assets: DemoAsset[];
  risk: DemoRisk;
  migration: DemoMigration;
  verification: DemoVerification;
};

export type DemoEvent = {
  step: DemoStep["id"];
  message: string;
  progress: number;
};
