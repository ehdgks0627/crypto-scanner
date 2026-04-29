import { describe, expect, it } from "vitest";

import { buildDiscoveryCreatePayload } from "./discoveryCreatePayload";

describe("buildDiscoveryCreatePayload", () => {
  it("parses valid comma separated ports", () => {
    expect(buildDiscoveryCreatePayload(" 172.20.0.0/24 ", "443, 22,500", true)).toEqual({
      payload: {
        cidr: "172.20.0.0/24",
        ports: [443, 22, 500],
        include_default_ports: true
      },
      errors: []
    });
  });

  it("rejects duplicate ports", () => {
    const result = buildDiscoveryCreatePayload("172.20.0.0/24", "443,443", false);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("Ports must be unique integers between 1 and 65535.");
  });

  it("rejects non-integer and out-of-range ports", () => {
    expect(buildDiscoveryCreatePayload("172.20.0.0/24", "443.5", false).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("172.20.0.0/24", "65536", false).payload).toBeNull();
    expect(buildDiscoveryCreatePayload("172.20.0.0/24", "0", false).payload).toBeNull();
  });

  it("allows blank ports when defaults are included", () => {
    expect(buildDiscoveryCreatePayload("172.20.0.0/24", "", true)).toEqual({
      payload: {
        cidr: "172.20.0.0/24",
        ports: [],
        include_default_ports: true
      },
      errors: []
    });
  });

  it("requires cidr", () => {
    const result = buildDiscoveryCreatePayload("", "443", true);

    expect(result.payload).toBeNull();
    expect(result.errors).toContain("CIDR is required.");
  });
});
