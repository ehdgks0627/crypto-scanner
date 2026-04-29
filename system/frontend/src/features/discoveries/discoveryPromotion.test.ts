import { describe, expect, it } from "vitest";

import { DiscoveryPromotionModel } from "./discoveryPromotion";

describe("DiscoveryPromotionModel", () => {
  const endpoints = [
    {
      id: 1,
      ip: "10.0.0.1",
      port: 443,
      detected_protocol: "HTTPS",
      banner_metadata: {},
      promoted: false,
      target_id: null,
      suggested_protocol_hint: "TLS",
      suggested_host: "web.testbed.local"
    },
    {
      id: 2,
      ip: "10.0.0.2",
      port: 22,
      detected_protocol: "SSH",
      banner_metadata: {},
      promoted: true,
      target_id: 8,
      suggested_protocol_hint: "SSH",
      suggested_host: "ssh.testbed.local"
    }
  ] as const;

  it("requires explicit selection and never promotes all by default", () => {
    const model = new DiscoveryPromotionModel([...endpoints]);

    expect(model.promotableIds()).toEqual([1]);
    expect(model.payloadForSelected([])).toEqual([]);
  });

  it("builds promotion payload only for selected unpromoted endpoints", () => {
    const model = new DiscoveryPromotionModel([...endpoints]);

    expect(model.payloadForSelected([1, 2])).toEqual([
      {
        endpoint_id: 1,
        host: "web.testbed.local",
        protocol_hint: "TLS",
        agent_enabled: false
      }
    ]);
  });

  it("falls back to ip and UNKNOWN when suggestions are absent", () => {
    const model = new DiscoveryPromotionModel([
      {
        id: 3,
        ip: "10.0.0.3",
        port: 500,
        detected_protocol: null,
        banner_metadata: {},
        promoted: false,
        target_id: null,
        suggested_protocol_hint: null,
        suggested_host: null
      }
    ]);

    expect(model.payloadForSelected([3])).toEqual([
      {
        endpoint_id: 3,
        host: "10.0.0.3",
        protocol_hint: "UNKNOWN",
        agent_enabled: false
      }
    ]);
  });
});
