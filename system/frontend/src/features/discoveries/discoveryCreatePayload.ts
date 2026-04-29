import type { Schema } from "../../api/types";

export type DiscoveryCreateParseResult = {
  payload: Schema<"DiscoveryCreate"> | null;
  errors: string[];
};

export function buildDiscoveryCreatePayload(cidr: string, portsText: string, includeDefaultPorts: boolean): DiscoveryCreateParseResult {
  const ports = parsePorts(portsText);
  const errors: string[] = [];

  if (!cidr.trim()) {
    errors.push("CIDR is required.");
  }
  if (!ports.valid) {
    errors.push("Ports must be unique integers between 1 and 65535.");
  }
  if (errors.length > 0) {
    return { payload: null, errors };
  }

  return {
    payload: {
      cidr: cidr.trim(),
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
