import type { Schema } from "../../api/types";

export type DiscoveryScopeType = Schema<"DiscoveryScopeType">;

export type DiscoveryCreateParseResult = {
  payload: Schema<"DiscoveryCreate"> | null;
  errors: string[];
};

export function buildDiscoveryCreatePayload(
  scopeType: DiscoveryScopeType,
  scopeValue: string,
  portsText: string,
  includeDefaultPorts: boolean
): DiscoveryCreateParseResult {
  const ports = parsePorts(portsText);
  const errors: string[] = [];
  const normalizedScopeValue = scopeValue.trim();

  if (!normalizedScopeValue) {
    errors.push("탐색 대상 값이 필요합니다.");
  } else if (!isValidScopeValue(scopeType, normalizedScopeValue)) {
    errors.push("탐색 대상 형식이 올바르지 않습니다.");
  }
  if (!ports.valid) {
    errors.push("포트는 1부터 65535까지의 중복 없는 정수여야 합니다.");
  }
  if (errors.length > 0) {
    return { payload: null, errors };
  }

  return {
    payload: {
      scope_type: scopeType,
      scope_value: normalizedScopeValue,
      ports: ports.values,
      include_default_ports: includeDefaultPorts
    },
    errors: []
  };
}

function parsePorts(value: string): { valid: true; values: number[] } | { valid: false; values: number[] } {
  const parts = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const parsed = parts.map((item) => Number(item));
  const unique = Array.from(new Set(parsed));
  const valid = parsed.every((port) => Number.isInteger(port) && port >= 1 && port <= 65535) && unique.length === parsed.length;
  return valid ? { valid: true, values: parsed } : { valid: false, values: [] };
}

function isValidScopeValue(scopeType: DiscoveryScopeType, value: string): boolean {
  if (scopeType === "cidr") {
    return /^[0-9A-Fa-f:.]+\/\d{1,3}$/.test(value);
  }
  if (scopeType === "ip") {
    return /^[0-9A-Fa-f:.]+$/.test(value) && (value.includes(".") || value.includes(":"));
  }
  return value.length <= 253 && !/[/:]/.test(value) && value.split(".").every((label) => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label));
}
