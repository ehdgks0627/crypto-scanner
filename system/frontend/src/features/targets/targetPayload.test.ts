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

  it("includes a trimmed display name when provided", () => {
    expect(
      buildTargetPayload({ ...defaultTargetFormValues, host: "api.testbed.local", display_name: "  Web Server #2  " }, "create")
    ).toMatchObject({
      display_name: "Web Server #2"
    });
  });

  it("sends null for blank nullable fields in patch mode and preserves zero lifespan", () => {
    expect(
      buildTargetPayload(
        {
          ...defaultTargetFormValues,
          host: "api.testbed.local",
          display_name: "",
          ip: "",
          sni: "",
          agent_url: "",
          lifespan_years: "0"
        },
        "patch"
      )
    ).toMatchObject({
      display_name: null,
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
