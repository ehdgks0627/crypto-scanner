import { describe, expect, it } from "vitest";

import { buildDiscoveryCreatePayload, discoveryServiceOptions } from "./discoveryCreatePayload";

const allServiceIds = discoveryServiceOptions.map((service) => service.id);

describe("buildDiscoveryCreatePayload", () => {
  it("builds ports from selected services", () => {
    expect(buildDiscoveryCreatePayload("cidr", " 172.20.0.0/24 ", ["https", "ssh", "ike"])).toEqual({
      payload: {
        scope_type: "cidr",
        scope_value: "172.20.0.0/24",
        ports: [443, 22, 500, 4500],
        include_default_ports: false
      },
      errors: []
    });
  });

  it("rejects empty service selection", () => {
    const result = buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", []);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("하나 이상의 서비스를 선택하세요.");
  });

  it("resolves combined IP/domain scope values", () => {
    expect(buildDiscoveryCreatePayload("host", "10.0.0.8", ["https"]).payload).toMatchObject({
      scope_type: "ip",
      scope_value: "10.0.0.8"
    });
    expect(buildDiscoveryCreatePayload("host", "app.testbed.local", ["https"]).payload).toMatchObject({
      scope_type: "domain",
      scope_value: "app.testbed.local"
    });
  });

  it("requires scope value", () => {
    const result = buildDiscoveryCreatePayload("cidr", "", ["https"]);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("탐색 대상 값이 필요합니다.");
  });

  it("rejects malformed scope values", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.1", allServiceIds).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("host", "bad/domain", allServiceIds).payload).toBeNull();
  });
});
