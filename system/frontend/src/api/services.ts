import { apiClient, type ApiClient } from "./client";
import type { AssetType, JobStatus, ProtocolHint, QueryParams, RiskTier, Schema, ScannerId } from "./types";

abstract class BaseService {
  constructor(protected readonly client: ApiClient) {}
}

export class DashboardService extends BaseService {
  summary(snapshotId?: number) {
    return this.client.request<Schema<"DashboardSummary">>("/dashboard/summary", {
      query: { snapshot_id: snapshotId }
    });
  }
}

export class TargetService extends BaseService {
  list(query: QueryParams = {}) {
    return this.client.request<Schema<"TargetPage">>("/targets", { query });
  }

  create(payload: Schema<"TargetCreate">) {
    return this.client.request<Schema<"Target">>("/targets", { method: "POST", body: payload });
  }

  get(id: number) {
    return this.client.request<Schema<"Target">>(`/targets/${id}`);
  }

  patch(id: number, payload: Schema<"TargetPatch">) {
    return this.client.request<Schema<"TargetPatchResult">>(`/targets/${id}`, { method: "PATCH", body: payload });
  }

  delete(id: number) {
    return this.client.request<void>(`/targets/${id}`, { method: "DELETE" });
  }
}

export class DiscoveryService extends BaseService {
  list(status?: JobStatus) {
    return this.client.request<Schema<"DiscoveryPage">>("/discoveries", { query: { status } });
  }

  create(payload: Schema<"DiscoveryCreate">) {
    return this.client.request<Schema<"JobEnvelope">>("/discoveries", { method: "POST", body: payload });
  }

  get(id: number) {
    return this.client.request<Schema<"Discovery">>(`/discoveries/${id}`);
  }

  endpoints(id: number) {
    return this.client.request<Schema<"DiscoveredEndpointPage">>(`/discoveries/${id}/endpoints`, { query: { limit: 100 } });
  }

  promote(id: number, promotions: Schema<"DiscoveryPromotion">[]) {
    return this.client.request<Schema<"DiscoveryPromoteResult">>(`/discoveries/${id}/promote`, {
      method: "POST",
      body: { promotions }
    });
  }
}

export class JobService extends BaseService {
  list(status?: JobStatus) {
    return this.client.request<Schema<"JobEnvelopePage">>("/jobs", { query: { status } });
  }

  create(payload: { target_ids: number[]; scanners: ScannerId[] }) {
    return this.client.request<Schema<"JobEnvelope">>("/jobs", { method: "POST", body: payload });
  }

  get(id: number) {
    return this.client.request<Schema<"JobEnvelope">>(`/jobs/${id}`);
  }

  cancel(id: number) {
    return this.client.request<Schema<"JobEnvelope">>(`/jobs/${id}/cancel`, { method: "POST" });
  }

  logs(id: number) {
    return this.client.request<Schema<"ScanRunLogPage">>(`/jobs/${id}/logs`, { query: { limit: 100 } });
  }
}

export class SnapshotService extends BaseService {
  list() {
    return this.client.request<Schema<"CbomSnapshotPage">>("/snapshots", { query: { limit: 100 } });
  }

  get(id: number) {
    return this.client.request<Schema<"CbomSnapshot">>(`/snapshots/${id}`);
  }

  export(id: number, pretty = true) {
    return this.client.request<Record<string, unknown>>(`/snapshots/${id}/export`, { query: { pretty } });
  }

  diff(id: number, other: number) {
    return this.client.request<Schema<"CbomDiff">>(`/snapshots/${id}/diff`, { query: { other } });
  }

  assets(snapshotId: number, query: QueryParams = {}) {
    return this.client.request<Schema<"AssetListPage">>(`/snapshots/${snapshotId}/assets`, {
      query: { limit: 100, ...query }
    });
  }
}

export class AssetService extends BaseService {
  get(id: number) {
    return this.client.request<Schema<"AssetDetail">>(`/assets/${id}`);
  }

  patchContext(id: number, payload: Schema<"AssetContextPatch">) {
    return this.client.request<Schema<"AssetContextPatchResult">>(`/assets/${id}/context`, {
      method: "PATCH",
      body: payload
    });
  }

  qualitative(id: number) {
    return this.client.request<Schema<"QualitativeAssessment">>(`/assets/${id}/qualitative`, { method: "POST" });
  }
}

export class RiskService extends BaseService {
  list(snapshotId: number, query: QueryParams = {}) {
    return this.client.request<Schema<"RiskScorePage">>(`/snapshots/${snapshotId}/risks`, {
      query: { limit: 100, ...query }
    });
  }

  top(snapshotId: number, n = 10) {
    return this.client.request<Schema<"RiskScorePage">>(`/snapshots/${snapshotId}/risks/top`, { query: { n } });
  }

  weights() {
    return this.client.request<Schema<"RiskWeightsState">>("/risk/weights");
  }

  putWeights(payload: Schema<"RiskWeightsInput">) {
    return this.client.request<Schema<"RiskWeightsState">>("/risk/weights", { method: "PUT", body: payload });
  }

  recompute(snapshotId: number, weights: Schema<"RiskWeightsInput">, persist = false) {
    return this.client.request<Schema<"JobEnvelope">>(`/snapshots/${snapshotId}/recompute`, {
      method: "POST",
      body: { weights, persist_weights_as_default: persist }
    });
  }
}

export class MigrationService extends BaseService {
  plan(snapshotId: number, query: { min_score?: number; tier?: RiskTier[]; asset_type?: AssetType[]; target_id?: number; asset_ids?: number[] } = {}) {
    return this.client.request<Schema<"MigrationPlanPage">>(`/snapshots/${snapshotId}/migration-plan`, {
      query: { limit: 100, ...query }
    });
  }

  impact(snapshotId: number, assetIds: number[]) {
    return this.client.request<Schema<"MigrationImpact">>(`/snapshots/${snapshotId}/migration-plan/impact`, {
      query: { asset_ids: assetIds }
    });
  }
}

export class PerformanceService extends BaseService {
  listRuns(snapshotId: number, query: QueryParams = {}) {
    return this.client.request<Schema<"PerformanceEvaluationRunPage">>(`/snapshots/${snapshotId}/performance-runs`, {
      query: { limit: 100, ...query }
    });
  }

  getRun(snapshotId: number, runId: number) {
    return this.client.request<Schema<"PerformanceEvaluationRunDetail">>(`/snapshots/${snapshotId}/performance-runs/${runId}`);
  }

  createRun(snapshotId: number, payload: Schema<"PerformanceRunCreate">) {
    return this.client.request<Schema<"PerformanceEvaluationRun">>(`/snapshots/${snapshotId}/performance-runs`, {
      method: "POST",
      body: payload
    });
  }

  patchRun(snapshotId: number, runId: number, payload: Schema<"PerformanceRunPatch">) {
    return this.client.request<Schema<"PerformanceEvaluationRun">>(`/snapshots/${snapshotId}/performance-runs/${runId}`, {
      method: "PATCH",
      body: payload
    });
  }

  upsertResult(snapshotId: number, runId: number, payload: Schema<"PerformanceResultCreate">) {
    return this.client.request<Schema<"AssetPerformanceResult">>(`/snapshots/${snapshotId}/performance-runs/${runId}/results`, {
      method: "POST",
      body: payload
    });
  }

  history(assetId: number) {
    return this.client.request<Schema<"AssetPerformanceResultPage">>(`/assets/${assetId}/performance-history`, {
      query: { limit: 100 }
    });
  }
}

export class AgentService extends BaseService {
  list(active?: boolean) {
    return this.client.request<Schema<"AgentPage">>("/agents", { query: { active, limit: 100 } });
  }

  get(id: string) {
    return this.client.request<Schema<"Agent">>(`/agents/${id}`);
  }

  delete(id: string) {
    return this.client.request<void>(`/agents/${id}`, { method: "DELETE" });
  }
}

export class MetaService extends BaseService {
  protocols() {
    return this.client.request<Schema<"ProtocolMeta">>("/meta/protocols");
  }

  scanners() {
    return this.client.request<Schema<"ScannerMeta">>("/meta/scanners");
  }

  algorithmRiskTable() {
    return this.client.request<Schema<"AlgorithmRiskTable">>("/meta/algorithm-risk-table");
  }
}

export class HealthService extends BaseService {
  get() {
    return this.client.request<Schema<"HealthStatus">>("/health");
  }
}

export const services = {
  dashboard: new DashboardService(apiClient),
  targets: new TargetService(apiClient),
  discoveries: new DiscoveryService(apiClient),
  jobs: new JobService(apiClient),
  snapshots: new SnapshotService(apiClient),
  assets: new AssetService(apiClient),
  risk: new RiskService(apiClient),
  migration: new MigrationService(apiClient),
  performance: new PerformanceService(apiClient),
  agents: new AgentService(apiClient),
  meta: new MetaService(apiClient),
  health: new HealthService(apiClient)
};

export const protocolOptions: ProtocolHint[] = ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"];
