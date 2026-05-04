import type { AssetType, JobStatus, RiskTier, Schema } from "../api/types";
import { riskTierLabels, statusLabels } from "./models";

type AssetContextField = keyof Schema<"AssetContextValues">;

const extraStatusLabels: Record<string, string> = {
  SUCCESS: "성공",
  PARTIAL: "부분 완료",
  TIMEOUT: "타임아웃",
  UNREACHABLE: "접속 불가",
  ERROR: "오류",
  SKIPPED: "건너뜀"
};

const performanceStatusLabels: Record<string, string> = {
  PENDING: "대기",
  RUNNING: "실행 중",
  COMPLETED: "완료",
  FAILED: "실패",
  PASS: "정상",
  WARN: "경고",
  FAIL: "실패",
  ERROR: "오류"
};

const jobKindLabels: Record<string, string> = {
  scan_job: "스캔",
  discovery: "탐색",
  recompute: "재계산"
};

const resourceKindLabels: Record<string, string> = {
  job: "작업",
  snapshot: "스냅샷",
  target: "스캔 대상",
  discovery: "탐색 작업",
  asset: "자산"
};

const assetClassLabels: Record<string, string> = {
  crypto: "암호",
  host: "호스트",
  service: "서비스",
  data: "데이터"
};

const assetTypeLabels: Record<AssetType | string, string> = {
  algorithm: "알고리즘",
  certificate: "인증서",
  key: "키",
  protocol: "프로토콜",
  keystore: "키 저장소",
  device: "장비",
  service: "서비스",
  data: "데이터"
};

const levelLabels: Record<string, string> = {
  low: "낮음",
  medium: "보통",
  high: "높음",
  critical: "치명"
};

const exposureLabels: Record<string, string> = {
  public_internet: "인터넷 공개",
  dmz: "DMZ",
  internal_network: "내부망",
  air_gapped: "망분리"
};

const contextFieldLabels: Record<AssetContextField, string> = {
  sensitivity: "민감도",
  lifespan_years: "보호 기간(년)",
  criticality: "중요도",
  exposure: "노출 범위",
  service_role: "서비스 역할"
};

const profileLabels: Record<string, string> = {
  smoke: "스모크",
  baseline: "기준",
  canary: "카나리",
  stress: "스트레스"
};

const agilityLevelLabels: Record<string, string> = {
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음"
};

const relationLabels: Record<string, string> = {
  exposes: "노출",
  presents: "제공",
  supports: "지원",
  uses: "사용",
  has_finding: "위험 발견",
  "has finding": "위험 발견"
};

export function riskTierLabel(tier?: RiskTier | string | null) {
  return tier ? riskTierLabels[tier as RiskTier] ?? tier : "-";
}

export function statusLabel(status?: JobStatus | string | null) {
  return status ? statusLabels[status as JobStatus] ?? extraStatusLabels[status] ?? status : "-";
}

export function performanceStatusLabel(status?: string | null) {
  return status ? performanceStatusLabels[status] ?? status : "-";
}

export function jobKindLabel(kind?: string | null) {
  return kind ? jobKindLabels[kind] ?? kind : "-";
}

export function resourceKindLabel(kind?: string | null) {
  return kind ? resourceKindLabels[kind] ?? kind : "-";
}

export function assetClassLabel(assetClass?: string | null) {
  return assetClass ? assetClassLabels[assetClass] ?? assetClass : "-";
}

export function assetTypeLabel(assetType?: AssetType | string | null) {
  return assetType ? assetTypeLabels[assetType] ?? assetType : "-";
}

export function levelLabel(level?: string | null) {
  return level ? levelLabels[level] ?? level : "-";
}

export function exposureLabel(exposure?: string | null) {
  return exposure ? exposureLabels[exposure] ?? exposure : "-";
}

export function contextFieldLabel(field: string) {
  return (contextFieldLabels as Record<string, string>)[field] ?? field;
}

export function contextValueLabel(field: string, value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (field === "sensitivity" || field === "criticality") {
    return levelLabel(String(value));
  }
  if (field === "exposure") {
    return exposureLabel(String(value));
  }
  return String(value);
}

export function profileLabel(profile?: string | null) {
  return profile ? profileLabels[profile] ?? profile : "-";
}

export function agilityLevelLabel(level?: string | null) {
  return level ? agilityLevelLabels[level] ?? level : "-";
}

export function relationLabel(kind?: string | null) {
  return kind ? relationLabels[kind] ?? kind.replace("_", " ") : "-";
}

export function enabledLabel(enabled: boolean) {
  return enabled ? "사용" : "미사용";
}

export function yesNoLabel(value: boolean) {
  return value ? "예" : "아니오";
}
