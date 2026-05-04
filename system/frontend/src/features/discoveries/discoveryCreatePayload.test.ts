import { describe, expect, it } from "vitest";

import { buildDiscoveryCreatePayload } from "./discoveryCreatePayload";

describe("buildDiscoveryCreatePayload", () => {
  it("parses valid comma separated ports", () => {
    expect(buildDiscoveryCreatePayload("cidr", " 172.20.0.0/24 ", "443, 22,500", true)).toEqual({
      payload: {
        scope_type: "cidr",
        scope_value: "172.20.0.0/24",
        ports: [443, 22, 500],
        include_default_ports: true
      },
      errors: []
    });
  });

  it("rejects duplicate ports", () => {
    const result = buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", "443,443", false);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("포트는 1부터 65535까지의 중복 없는 정수여야 합니다.");
  });

  it("rejects non-integer and out-of-range ports", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", "443.5", false).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", "65536", false).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", "0", false).payload).toBeNull();
  });

  it("allows blank ports when defaults are included", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.0/24", "", true)).toEqual({
      payload: {
        scope_type: "cidr",
        scope_value: "172.20.0.0/24",
        ports: [],
        include_default_ports: true
      },
      errors: []
    });
  });

  it("accepts IP and domain scopes", () => {
    expect(buildDiscoveryCreatePayload("ip", "10.0.0.8", "443", true).payload).toMatchObject({
      scope_type: "ip",
      scope_value: "10.0.0.8"
    });
    expect(buildDiscoveryCreatePayload("domain", "app.testbed.local", "443", true).payload).toMatchObject({
      scope_type: "domain",
      scope_value: "app.testbed.local"
    });
  });

  it("requires scope value", () => {
    const result = buildDiscoveryCreatePayload("cidr", "", "443", true);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("탐색 대상 값이 필요합니다.");
  });

  it("rejects malformed scope values", () => {
    expect(buildDiscoveryCreatePayload("cidr", "172.20.0.1", "443", true).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("ip", "not-an-ip", "443", true).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("domain", "bad/domain", "443", true).payload).toBeNull();
  });
});
