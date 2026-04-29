import { type FormEvent, useState } from "react";

import type { Schema } from "../../api/types";
import { Button } from "../../components/ui/button";
import { Checkbox, Field, FieldLabel, Input, Select } from "../../components/ui/form";
import { buildTargetPayload, defaultTargetFormValues, type TargetFormMode, type TargetFormValues } from "./targetPayload";

const levels = ["", "low", "medium", "high", "critical"];
const exposures = ["", "public_internet", "dmz", "internal_network", "air_gapped"];

export function TargetForm({
  initialValue,
  mode = "create",
  submitLabel,
  isSubmitting = false,
  onSubmit,
  onCancel
}: {
  initialValue?: Partial<TargetFormValues>;
  mode?: TargetFormMode;
  submitLabel: string;
  isSubmitting?: boolean;
  onSubmit: (payload: Schema<"TargetCreate"> | Schema<"TargetPatch">) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState<TargetFormValues>({ ...defaultTargetFormValues, ...initialValue });
  const portNumber = Number(values.port);
  const portValid = Number.isInteger(portNumber) && portNumber >= 1 && portNumber <= 65535;

  const setValue = <K extends keyof TargetFormValues>(key: K, value: TargetFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!portValid) {
      return;
    }
    onSubmit(buildTargetPayload(values, mode));
  };

  return (
    <form onSubmit={handleSubmit}>
      <fieldset className="form-fieldset" disabled={isSubmitting}>
        <div className="form-grid">
          <Field>
            <FieldLabel>Host</FieldLabel>
            <Input required value={values.host} onChange={(event) => setValue("host", event.target.value)} placeholder="api.internal.local" />
          </Field>
          <Field>
            <FieldLabel>IP</FieldLabel>
            <Input value={values.ip} onChange={(event) => setValue("ip", event.target.value)} placeholder="10.0.0.12" />
          </Field>
          <Field>
            <FieldLabel>Port</FieldLabel>
            <Input required type="number" min={1} max={65535} value={values.port} onChange={(event) => setValue("port", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Protocol</FieldLabel>
            <Select value={values.protocol_hint} onChange={(event) => setValue("protocol_hint", event.target.value as Schema<"ProtocolHint">)}>
              {["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"].map((protocol) => (
                <option key={protocol} value={protocol}>
                  {protocol}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <FieldLabel>Transport</FieldLabel>
            <Select value={values.transport} onChange={(event) => setValue("transport", event.target.value as Schema<"Transport">)}>
              <option value="TCP">TCP</option>
              <option value="UDP">UDP</option>
            </Select>
          </Field>
          <Field>
            <FieldLabel>SNI</FieldLabel>
            <Input value={values.sni} onChange={(event) => setValue("sni", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Agent URL</FieldLabel>
            <Input value={values.agent_url} onChange={(event) => setValue("agent_url", event.target.value)} placeholder="http://agent.local:9100" />
          </Field>
          <Field>
            <FieldLabel>Agent</FieldLabel>
            <span className="inline-actions">
              <Checkbox checked={values.agent_enabled} onChange={(event) => setValue("agent_enabled", event.target.checked)} />
              <span>Agent 사용</span>
            </span>
          </Field>
          <Field>
            <FieldLabel>Sensitivity</FieldLabel>
            <Select value={values.sensitivity} onChange={(event) => setValue("sensitivity", event.target.value)}>
              {levels.map((level) => (
                <option key={level || "empty"} value={level}>
                  {level || "inherit"}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <FieldLabel>Criticality</FieldLabel>
            <Select value={values.criticality} onChange={(event) => setValue("criticality", event.target.value)}>
              {levels.map((level) => (
                <option key={level || "empty"} value={level}>
                  {level || "inherit"}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <FieldLabel>Exposure</FieldLabel>
            <Select value={values.exposure} onChange={(event) => setValue("exposure", event.target.value)}>
              {exposures.map((exposure) => (
                <option key={exposure || "empty"} value={exposure}>
                  {exposure || "inherit"}
                </option>
              ))}
            </Select>
          </Field>
          <Field>
            <FieldLabel>Lifespan Years</FieldLabel>
            <Input type="number" min={0} value={values.lifespan_years} onChange={(event) => setValue("lifespan_years", event.target.value)} />
          </Field>
          <Field className="is-wide">
            <FieldLabel>Service Role</FieldLabel>
            <Input value={values.service_role} onChange={(event) => setValue("service_role", event.target.value)} placeholder="web-frontend" />
          </Field>
        </div>
        {!portValid ? <div className="callout state-view--error" role="alert">Port는 1부터 65535 사이의 정수여야 합니다.</div> : null}
        <div className="form-actions">
          {onCancel ? (
            <Button type="button" variant="ghost" onClick={onCancel}>
              취소
            </Button>
          ) : null}
          <Button type="submit" variant="primary" disabled={!portValid || isSubmitting}>
            {isSubmitting ? "저장 중" : submitLabel}
          </Button>
        </div>
      </fieldset>
    </form>
  );
}

export function targetToFormValues(target: Schema<"Target">): Partial<TargetFormValues> {
  return {
    host: target.host,
    ip: target.ip ?? "",
    port: String(target.port),
    protocol_hint: target.protocol_hint,
    transport: target.transport,
    sni: target.sni ?? "",
    agent_enabled: target.agent_enabled,
    agent_url: target.agent_url ?? "",
    sensitivity: target.context.sensitivity ?? "",
    lifespan_years: target.context.lifespan_years == null ? "" : String(target.context.lifespan_years),
    criticality: target.context.criticality ?? "",
    exposure: target.context.exposure ?? "",
    service_role: target.context.service_role ?? ""
  };
}
