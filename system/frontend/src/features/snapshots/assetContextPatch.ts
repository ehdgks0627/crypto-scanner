import type { Schema } from "../../api/types";

export type AssetContextFormValues = Record<keyof Schema<"AssetContextValues">, string>;
export type AssetContextEnabledFields = Record<keyof Schema<"AssetContextValues">, boolean>;

const contextFields: Array<keyof Schema<"AssetContextValues">> = [
  "sensitivity",
  "lifespan_years",
  "criticality",
  "exposure",
  "service_role"
];

export function buildAssetContextPatch(
  initialValue: Schema<"AssetContextValues">,
  values: AssetContextFormValues,
  enabled: AssetContextEnabledFields
): Schema<"AssetContextPatch"> {
  const validationError = validateAssetContextPatchValues(values, enabled);
  if (validationError) {
    throw new Error(validationError);
  }

  const payload: Schema<"AssetContextPatch"> = {};

  contextFields.forEach((field) => {
    if (enabled[field]) {
      if (field === "lifespan_years") {
        payload[field] = values[field] === "" ? null : Number(values[field]);
        return;
      }
      payload[field] = (values[field] || null) as never;
      return;
    }
    if (initialValue[field] !== null) {
      payload[field] = null as never;
    }
  });

  return payload;
}

export function validateAssetContextPatchValues(values: AssetContextFormValues, enabled: AssetContextEnabledFields): string | null {
  if (!enabled.lifespan_years || values.lifespan_years === "") {
    return null;
  }
  const parsed = Number(values.lifespan_years);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return "Lifespan years는 0 이상의 정수여야 합니다.";
  }
  return null;
}

export function assetContextToFormValues(initialValue: Schema<"AssetContextValues">): AssetContextFormValues {
  return {
    sensitivity: initialValue.sensitivity ?? "",
    lifespan_years: initialValue.lifespan_years == null ? "" : String(initialValue.lifespan_years),
    criticality: initialValue.criticality ?? "",
    exposure: initialValue.exposure ?? "",
    service_role: initialValue.service_role ?? ""
  };
}

export function assetContextEnabledFields(initialValue: Schema<"AssetContextValues">): AssetContextEnabledFields {
  return {
    sensitivity: initialValue.sensitivity !== null,
    lifespan_years: initialValue.lifespan_years !== null,
    criticality: initialValue.criticality !== null,
    exposure: initialValue.exposure !== null,
    service_role: initialValue.service_role !== null
  };
}

export const assetContextFields = contextFields;
