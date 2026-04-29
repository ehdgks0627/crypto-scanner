import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError, createRequestId } from "./client";
import { DiscoveryService, RiskService } from "./services";

describe("ApiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serializes arrays as CSV query params and returns JSON", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      expect(request.url).toBe("http://example.test/api/snapshots/7/risks?tier=CRITICAL%2CHIGH");
      expect(request.headers.get("Accept")).toBe("application/json, application/*+json");
      return new Response(JSON.stringify({ items: [], total: 0, offset: 0, limit: 20 }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = new ApiClient("http://example.test/api");
    const response = await client.request("/snapshots/7/risks", { query: { tier: ["CRITICAL", "HIGH"] } });

    expect(response).toEqual({ items: [], total: 0, offset: 0, limit: 20 });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("falls back when crypto.randomUUID is unavailable on non-secure HTTP pages", async () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (array: Uint8Array) => {
        array.fill(0x11);
        return array;
      }
    });
    const requestId = createRequestId();

    expect(requestId).toBe("11111111-1111-4111-9111-111111111111");
  });

  it("normalizes API error envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: "job_not_cancellable", message: "Job is not cancellable.", details: { job_id: 3 } }), {
          status: 409,
          headers: { "Content-Type": "application/json", "X-Request-Id": "req-1" }
        })
      )
    );

    const client = new ApiClient("http://example.test/api");
    await expect(client.request("/jobs/3/cancel", { method: "POST" })).rejects.toMatchObject({
      status: 409,
      errorCode: "job_not_cancellable",
      requestId: "req-1"
    });
  });

  it("sends discovery promotion using the OpenAPI request envelope", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      expect(request.url).toBe("http://example.test/api/discoveries/4/promote");
      expect(await request.json()).toEqual({
        promotions: [{ endpoint_id: 9, host: "web.testbed.local", protocol_hint: "TLS", agent_enabled: false }]
      });
      return new Response(JSON.stringify({ promoted: [{ endpoint_id: 9, target_id: 12 }], skipped: [] }), {
        status: 201,
        headers: { "Content-Type": "application/json" }
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const service = new DiscoveryService(new ApiClient("http://example.test/api"));
    const result = await service.promote(4, [{ endpoint_id: 9, host: "web.testbed.local", protocol_hint: "TLS", agent_enabled: false }]);

    expect(result.promoted).toHaveLength(1);
  });

  it("sends risk recompute persist flag with the contract field name", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      expect(request.url).toBe("http://example.test/api/snapshots/7/recompute");
      expect(await request.json()).toEqual({
        weights: { wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 },
        persist_weights_as_default: true
      });
      return new Response(
        JSON.stringify({
          id: 2,
          kind: "recompute",
          resource: { kind: "recompute", id: 2 },
          status: "PENDING",
          progress: null,
          started_at: null,
          cancel_requested_at: null,
          finished_at: null,
          result: null,
          error: null
        }),
        { status: 202, headers: { "Content-Type": "application/json" } }
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const service = new RiskService(new ApiClient("http://example.test/api"));
    const result = await service.recompute(7, { wA: 1, wD: 1, wE: 1, wL: 1, wC: 1 }, true);

    expect(result.kind).toBe("recompute");
  });
});
