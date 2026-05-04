import type { Schema } from "../../api/types";

export type DiscoveryScopeType = Schema<"DiscoveryScopeType">;
export type DiscoveryScopeInputType = "cidr" | "host";
export type DiscoveryExecutorType = Schema<"DiscoveryExecutorType">;

export const discoveryServiceOptions = [
  { id: "https-web", label: "HTTPS Web Server", ports: [443] },
  { id: "pqc-tls", label: "PQC-enabled TLS Server", ports: [443] },
  { id: "ssh", label: "SSH Server", ports: [22, 2222] },
  { id: "mqtt", label: "MQTT Broker", ports: [8883] },
  { id: "ipsec", label: "IPsec Gateway", ports: [500, 4500] },
  { id: "mail", label: "Mail Server", ports: [25, 465, 587, 993, 995] },
  { id: "postgresql", label: "Database Server", ports: [5432] },
  { id: "api-gateway", label: "API Gateway", ports: [8443] },
  { id: "admin-console", label: "Admin Console", ports: [443] },
  { id: "mobile-api", label: "Mobile API", ports: [443] },
  { id: "auth-oidc", label: "OIDC Provider", ports: [443] },
  { id: "saml-idp", label: "SAML Identity Provider", ports: [443] },
  { id: "mysql-legacy", label: "Legacy MySQL TLS", ports: [3306] },
  { id: "redis-cache", label: "Redis Cache TLS", ports: [6380] },
  { id: "kafka-broker", label: "Kafka Broker TLS", ports: [9093] },
  { id: "internal-grpc", label: "Internal gRPC Service", ports: [8443] },
  { id: "service-mesh-mtls", label: "Service Mesh mTLS Control Plane", ports: [15017] },
  { id: "gitlab-runner", label: "CI Runner Control", ports: [9443] },
  { id: "container-registry", label: "Container Registry", ports: [5000] },
  { id: "artifact-repo", label: "Artifact Repository", ports: [8443] },
  { id: "vault", label: "Vault KMS", ports: [8200] },
  { id: "backup-service", label: "Backup Encryption Service", ports: [8443] },
  { id: "monitoring", label: "Monitoring", ports: [9090] },
  { id: "logging", label: "Logging Search", ports: [9200] },
  { id: "legacy-java-app", label: "Legacy Java App", ports: [8443] }
] as const;

export type DiscoveryServiceId = (typeof discoveryServiceOptions)[number]["id"];

export type DiscoveryCreateParseResult = {
  payload: Schema<"DiscoveryCreate"> | null;
  errors: string[];
};

export function buildDiscoveryCreatePayload(
  scopeType: DiscoveryScopeInputType,
  scopeValue: string,
  serviceIds: DiscoveryServiceId[],
  executorType: DiscoveryExecutorType = "central",
  agentId?: string
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
  if (executorType === "agent" && !agentId) {
    errors.push("Discovery Agent를 선택하세요.");
  }
  if (errors.length > 0) {
    return { payload: null, errors };
  }

  const payloadScopeType = resolvePayloadScopeType(scopeType, normalizedScopeValue);

  return {
    payload: {
      scope_type: payloadScopeType,
      scope_value: normalizedScopeValue,
      executor_type: executorType,
      agent_id: executorType === "agent" ? agentId : undefined,
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
