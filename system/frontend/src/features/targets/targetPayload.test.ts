import { describe, expect, it } from "vitest";

import { buildTargetPayload, defaultTargetFormValues } from "./targetPayload";

describe("buildTargetPayload", () => {
  it("omits blank nullable fields for create payloads", () => {
    expect(buildTargetPayload({ ...defaultTargetFormValues, host: "api.testbed.local" }, "create")).toEqual({
      host: "api.testbed.local",
      port: 443,
      protocol_hint: "TLS",
      transport: "TCP",
      agent_enabled: false
    });
  });

  it("sends null for blank nullable fields in patch mode and preserves zero lifespan", () => {
    expect(
      buildTargetPayload(
        {
          ...defaultTargetFormValues,
          host: "api.testbed.local",
          ip: "",
          sni: "",
          agent_url: "",
          lifespan_years: "0"
        },
        "patch"
      )
    ).toMatchObject({
      ip: null,
      sni: null,
      agent_url: null,
      context: {
        sensitivity: null,
        lifespan_years: 0,
        criticality: null,
        exposure: null,
        service_role: null
      }
    });
  });
});
