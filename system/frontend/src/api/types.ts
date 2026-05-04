import type { components } from "./generated/types";

export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];

export type Page<T> = {
  items: T[];
  total: number;
  offset: number;
  limit: number;
};

export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined | Array<string | number | boolean>
>;

export type RiskTier = Schema<"RiskTier">;
export type AssetType = Schema<"AssetType">;
export type JobStatus = Schema<"JobStatus">;
export type JobKind = Schema<"JobKind">;
export type ScannerId = Schema<"ScannerId">;
export type AgentRole = Schema<"AgentRole">;
export type ProtocolHint = Schema<"ProtocolHint">;
export type TargetContext = Schema<"TargetContext">;
export type RiskWeightsInput = Schema<"RiskWeightsInput">;
