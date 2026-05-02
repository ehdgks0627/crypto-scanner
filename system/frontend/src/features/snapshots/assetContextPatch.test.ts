import { describe, expect, it } from "vitest";

import { assetContextToFormValues, buildAssetContextPatch, validateAssetContextPatchValues } from "./assetContextPatch";

const initial = {
  sensitivity: "high",
  lifespan_years: 0,
  criticality: null,
  exposure: "internal_network",
  service_role: null
} as const;

describe("buildAssetContextPatch", () => {
  it("uses blank form values as clear requests and sends changed values only", () => {
    const values = assetContextToFormValues(initial);
    values.sensitivity = "";
    values.criticality = "critical";

    expect(buildAssetContextPatch(initial, values)).toEqual({
      sensitivity: null,
      criticality: "critical"
    });
  });

  it("preserves zero lifespan and treats blank text values as null", () => {
    const values = assetContextToFormValues(initial);
    values.lifespan_years = "1";
    values.lifespan_years = "0";
    values.service_role = "";

    expect(buildAssetContextPatch(initial, values)).toEqual({});

    values.lifespan_years = "";
    expect(buildAssetContextPatch(initial, values)).toEqual({ lifespan_years: null });
  });

  it("rejects negative, decimal, and non-numeric lifespan values", () => {
    const values = assetContextToFormValues(initial);

    values.lifespan_years = "-1";
    expect(validateAssetContextPatchValues(values)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");
    expect(() => buildAssetContextPatch(initial, values)).toThrow(/Lifespan years/);

    values.lifespan_years = "1.5";
    expect(validateAssetContextPatchValues(values)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");

    values.lifespan_years = "abc";
    expect(validateAssetContextPatchValues(values)).toBe("Lifespan years는 0 이상의 정수여야 합니다.");
  });
});
