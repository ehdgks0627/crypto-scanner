import type { Schema } from "../../api/types";
import { compactObject } from "../../lib/utils";

export type TargetFormValues = {
  host: string;
  ip: string;
  port: string;
  protocol_hint: Schema<"ProtocolHint">;
  transport: Schema<"Transport">;
  sni: string;
  agent_enabled: boolean;
  agent_url: string;
  sensitivity: string;
  lifespan_years: string;
  criticality: string;
  exposure: string;
  service_role: string;
};

export type TargetFormMode = "create" | "patch";

export const defaultTargetFormValues: TargetFormValues = {
  host: "",
  ip: "",
  port: "443",
  protocol_hint: "TLS",
  transport: "TCP",
  sni: "",
  agent_enabled: false,
  agent_url: "",
  sensitivity: "",
  lifespan_years: "",
  criticality: "",
  exposure: "",
  service_role: ""
};

export function buildTargetPayload(values: TargetFormValues, mode: TargetFormMode): Schema<"TargetCreate"> | Schema<"TargetPatch"> {
  const context = buildContextPayload(values, mode);
  const base = {
    host: values.host,
    ip: nullableText(values.ip, mode),
    port: Number(values.port),
    protocol_hint: values.protocol_hint,
    transport: values.transport,
    sni: nullableText(values.sni, mode),
    agent_enabled: values.agent_enabled,
    agent_url: nullableText(values.agent_url, mode),
    context
  };

  if (mode === "patch") {
    return base as Schema<"TargetPatch">;
  }

  return compactObject(base) as Schema<"TargetCreate">;
}

function buildContextPayload(values: TargetFormValues, mode: TargetFormMode): Schema<"TargetContext"> | undefined {
  const context = {
    sensitivity: nullableText(values.sensitivity, mode),
    lifespan_years: nullableNumber(values.lifespan_years, mode),
    criticality: nullableText(values.criticality, mode),
    exposure: nullableText(values.exposure, mode),
    service_role: nullableText(values.service_role, mode)
  };

  if (mode === "patch") {
    return context as Schema<"TargetContext">;
  }

  const compacted = compactObject(context) as Schema<"TargetContext">;
  return Object.keys(compacted).length > 0 ? compacted : undefined;
}

function nullableText(value: string, mode: TargetFormMode): string | null | undefined {
  const trimmed = value.trim();
  if (trimmed) {
    return trimmed;
  }
  return mode === "patch" ? null : undefined;
}

function nullableNumber(value: string, mode: TargetFormMode): number | null | undefined {
  if (value.trim() === "") {
    return mode === "patch" ? null : undefined;
  }
  return Number(value);
}
