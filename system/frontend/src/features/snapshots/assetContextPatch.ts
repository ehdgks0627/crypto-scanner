import type { Schema } from "../../api/types";

export type AssetContextFormValues = Record<keyof Schema<"AssetContextValues">, string>;

const contextFields: Array<keyof Schema<"AssetContextValues">> = [
  "sensitivity",
  "lifespan_years",
  "criticality",
  "exposure",
  "service_role"
];

export function buildAssetContextPatch(
  initialValue: Schema<"AssetContextValues">,
  values: AssetContextFormValues
): Schema<"AssetContextPatch"> {
  const validationError = validateAssetContextPatchValues(values);
  if (validationError) {
    throw new Error(validationError);
  }

  const payload: Schema<"AssetContextPatch"> = {};

  contextFields.forEach((field) => {
    if (field === "lifespan_years") {
      const nextValue = values[field] === "" ? null : Number(values[field]);
      if (initialValue[field] !== nextValue) {
        payload[field] = nextValue;
      }
      return;
    }
    const nextValue = values[field] || null;
    if (initialValue[field] !== nextValue) {
      payload[field] = nextValue as never;
    }
  });

  return payload;
}

export function validateAssetContextPatchValues(values: AssetContextFormValues): string | null {
  if (values.lifespan_years === "") {
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

export const assetContextFields = contextFields;
