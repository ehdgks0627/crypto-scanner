import type { Schema } from "../../api/types";

export type DiscoveryScopeType = Schema<"DiscoveryScopeType">;
export type DiscoveryScopeInputType = "cidr" | "host";

export const discoveryServiceOptions = [
  { id: "https", label: "HTTPS / TLS", ports: [443] },
  { id: "ssh", label: "SSH", ports: [22] },
  { id: "mqtt", label: "MQTT over TLS", ports: [8883] },
  { id: "postgresql", label: "PostgreSQL TLS", ports: [5432] },
  { id: "ike", label: "IKE / IPsec", ports: [500, 4500] },
  { id: "smtp-starttls", label: "SMTP STARTTLS", ports: [25] },
  { id: "submission-starttls", label: "Submission STARTTLS", ports: [587] },
  { id: "smtps", label: "SMTPS", ports: [465] },
  { id: "imap-starttls", label: "IMAP STARTTLS", ports: [143] },
  { id: "imaps", label: "IMAPS", ports: [993] },
  { id: "pop3-starttls", label: "POP3 STARTTLS", ports: [110] },
  { id: "pop3s", label: "POP3S", ports: [995] }
] as const;

export type DiscoveryServiceId = (typeof discoveryServiceOptions)[number]["id"];

export type DiscoveryCreateParseResult = {
  payload: Schema<"DiscoveryCreate"> | null;
  errors: string[];
};

export function buildDiscoveryCreatePayload(
  scopeType: DiscoveryScopeInputType,
  scopeValue: string,
  serviceIds: DiscoveryServiceId[]
): DiscoveryCreateParseResult {
  const ports = portsForServices(serviceIds);
  const errors: string[] = [];
  const normalizedScopeValue = scopeValue.trim();

  if (!normalizedScopeValue) {
    errors.push("탐색 대상 값이 필요합니다.");
  } else if (!isValidScopeValue(scopeType, normalizedScopeValue)) {
    errors.push("탐색 대상 형식이 올바르지 않습니다.");
  }
  if (ports.length === 0) {
    errors.push("하나 이상의 서비스를 선택하세요.");
  }
  if (errors.length > 0) {
    return { payload: null, errors };
  }

  const payloadScopeType = resolvePayloadScopeType(scopeType, normalizedScopeValue);

  return {
    payload: {
      scope_type: payloadScopeType,
      scope_value: normalizedScopeValue,
      ports,
      include_default_ports: false
    },
    errors: []
  };
}

function portsForServices(serviceIds: DiscoveryServiceId[]): number[] {
  const selected = new Set(serviceIds);
  const ports = discoveryServiceOptions
    .filter((service) => selected.has(service.id))
    .flatMap((service) => service.ports);
  return Array.from(new Set(ports));
}

function isValidScopeValue(scopeType: DiscoveryScopeInputType, value: string): boolean {
  if (scopeType === "cidr") {
    return /^[0-9A-Fa-f:.]+\/\d{1,3}$/.test(value);
  }
  return isIpLiteral(value) || isDomainName(value);
}

function resolvePayloadScopeType(scopeType: DiscoveryScopeInputType, value: string): DiscoveryScopeType {
  if (scopeType === "cidr") {
    return "cidr";
  }
  return isIpLiteral(value) ? "ip" : "domain";
}

function isIpLiteral(value: string): boolean {
  return /^[0-9A-Fa-f:.]+$/.test(value) && (value.includes(".") || value.includes(":"));
}

function isDomainName(value: string): boolean {
  return value.length <= 253 && !/[/:]/.test(value) && value.split(".").every((label) => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label));
}
