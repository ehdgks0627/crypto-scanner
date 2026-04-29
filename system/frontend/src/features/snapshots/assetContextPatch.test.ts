import { describe, expect, it } from "vitest";

import { assetContextEnabledFields, assetContextToFormValues, buildAssetContextPatch, validateAssetContextPatchValues } from "./assetContextPatch";

const initial = {
  sensitivity: "high",
  lifespan_years: 0,
  criticality: null,
  exposure: "internal_network",
  service_role: null
} as const;

describe("buildAssetContextPatch", () => {
  it("sends only changed enabled fields and clear requests", () => {
    const values = assetContextToFormValues(initial);
    const enabled = assetContextEnabledFields(initial);
    enabled.sensitivity = false;
    enabled.criticality = true;
    values.criticality = "critical";

    expect(buildAssetContextPatch(initial, values, enabled)).toEqual({
      sensitivity: null,
      lifespan_years: 0,
      criticality: "critical",
      exposure: "internal_network"
    });
  });

  it("preserves zero lifespan and treats blank enabled values as null", () => {
    const values = assetContextToFormValues(initial);
    const enabled = assetContextEnabledFields(initial);
    enabled.service_role = true;
    values.service_role = "";

    expect(buildAssetContextPatch(initial, values, enabled)).toMatchObject({
      lifespan_years: 0,
      service_role: null
    });
  });

  it("rejects negative, decimal, and non-numeric lifespan values", () => {
    const values = assetContextToFormValues(initial);
    const enabled = assetContextEnabledFields(initial);
    enabled.lifespan_years = true;

    values.lifespan_years = "-1";
    expect(validateAssetContextPatchValues(values, enabled)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");
    expect(() => buildAssetContextPatch(initial, values, enabled)).toThrow(/Lifespan years/);

    values.lifespan_years = "1.5";
    expect(validateAssetContextPatchValues(values, enabled)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");

    values.lifespan_years = "abc";
    expect(validateAssetContextPatchValues(values, enabled)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");
  });
});
