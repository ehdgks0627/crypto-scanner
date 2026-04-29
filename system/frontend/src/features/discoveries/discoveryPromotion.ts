import type { ProtocolHint, Schema } from "../../api/types";

type Endpoint = Schema<"DiscoveredEndpoint">;

export class DiscoveryPromotionModel {
  constructor(private readonly endpoints: Endpoint[]) {}

  promotableIds(): number[] {
    return this.promotable().map((endpoint) => endpoint.id);
  }

  payloadForSelected(selectedIds: number[]): Schema<"DiscoveryPromotion">[] {
    if (selectedIds.length === 0) {
      return [];
    }

    const selected = new Set(selectedIds);
    return this.promotable()
      .filter((endpoint) => selected.has(endpoint.id))
      .map((endpoint) => ({
        endpoint_id: endpoint.id,
        host: endpoint.suggested_host ?? endpoint.ip,
        protocol_hint: (endpoint.suggested_protocol_hint ?? "UNKNOWN") as ProtocolHint,
        agent_enabled: false
      }));
  }

  private promotable(): Endpoint[] {
    return this.endpoints.filter((endpoint) => !endpoint.promoted);
  }
}
