import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { DiscoveriesView, DiscoveryDetailView } from "./DiscoveryViews";

describe("DiscoveriesView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("toggles Discovery #6 selection from the row checkbox", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.discoveries, "list").mockResolvedValue({
      items: [
        {
          id: 5,
          job_id: 105,
          scope_type: "cidr",
          scope_value: "172.20.5.0/24",
          cidr: "172.20.5.0/24",
          executor_type: "central",
          agent_id: null,
          agent_hostname: null,
          port_list: [443],
          status: "COMPLETED",
          created_at: "2026-04-29T00:00:00Z",
          started_at: "2026-04-29T00:00:01Z",
          finished_at: "2026-04-29T00:00:10Z",
          error: null
        },
        {
          id: 6,
          job_id: 106,
          scope_type: "cidr",
          scope_value: "172.20.6.0/24",
          cidr: "172.20.6.0/24",
          executor_type: "agent",
          agent_id: "9ab79c7e-76e8-4e49-a8b4-40be4d5a2f54",
          agent_hostname: "probe.dmz.testbed.local",
          port_list: [22, 443],
          status: "COMPLETED",
          created_at: "2026-04-29T00:01:00Z",
          started_at: "2026-04-29T00:01:01Z",
          finished_at: "2026-04-29T00:01:10Z",
          error: null
        }
      ],
      total: 2,
      offset: 0,
      limit: 20
    });

    renderWithApp(<DiscoveriesView />);

    const discoverySixCheckbox = await screen.findByLabelText("탐색 대상 #6 선택");
    expect(screen.getByText("probe.dmz.testbed.local")).toBeInTheDocument();
    expect(discoverySixCheckbox).not.toBeChecked();
    expect(screen.getByText("선택 0개")).toBeInTheDocument();

    await user.click(discoverySixCheckbox);

    expect(discoverySixCheckbox).toBeChecked();
    expect(screen.getByText("선택 1개")).toBeInTheDocument();

    await user.click(discoverySixCheckbox);

    expect(discoverySixCheckbox).not.toBeChecked();
    expect(screen.getByText("선택 0개")).toBeInTheDocument();
  });

  it("renders discovery availability report and endpoint checks", async () => {
    vi.spyOn(services.discoveries, "get").mockResolvedValue({
      id: 9,
      job_id: 109,
      scope_type: "cidr",
      scope_value: "172.20.0.0/24",
      cidr: "172.20.0.0/24",
      executor_type: "agent",
      agent_id: "9ab79c7e-76e8-4e49-a8b4-40be4d5a2f54",
      agent_hostname: "probe.dmz.testbed.local",
      port_list: [443],
      status: "COMPLETED",
      progress: { completed: 1, total: 1 },
      created_at: "2026-04-29T00:00:00Z",
      started_at: "2026-04-29T00:00:01Z",
      finished_at: "2026-04-29T00:00:10Z",
      error: null,
      availability_report: {
        measured_endpoint_count: 1,
        tls_endpoint_count: 1,
        sample_count: 3,
        averages: {
          tcp_connect_p95_ms: 4.2,
          handshake_p95_ms: 30.2,
          ttfb_p95_ms: 12.5,
          total_request_p95_ms: 15.8
        },
        max: {
          handshake_p95_ms: 31.4,
          ttfb_p95_ms: 12.5,
          total_request_p95_ms: 15.8
        },
        rates: {
          failure_rate: 0.05,
          timeout_rate: 0
        },
        handshake_bytes: {
          sent: 1632,
          received: 4216
        }
      }
    });
    vi.spyOn(services.discoveries, "endpoints").mockResolvedValue({
      items: [
        {
          id: 77,
          ip: "172.20.10.11",
          port: 443,
          detected_protocol: "TLS",
          banner_metadata: {},
          promoted: true,
          target_id: 31,
          suggested_protocol_hint: "TLS",
          suggested_host: "web.testbed.local",
          availability_metrics: {
            handshake_ms: { p95: 31.4 },
            ttfb_ms: { p95: 12.5 },
            failure_rate: 0.05
          }
        }
      ],
      total: 1,
      offset: 0,
      limit: 100
    });
    vi.spyOn(services.jobs, "get").mockResolvedValue({
      id: 109,
      kind: "discovery",
      resource: { kind: "discovery", id: 9 },
      status: "COMPLETED",
      progress: { completed: 1, total: 1 },
      started_at: "2026-04-29T00:00:01Z",
      cancel_requested_at: null,
      finished_at: "2026-04-29T00:00:10Z",
      result: { discovery_id: 9 },
      error: null
    });

    renderWithApp(<DiscoveryDetailView id={9} />);

    expect(await screen.findByText("가용성 검사 리포트")).toBeInTheDocument();
    expect(screen.getByText("스캔 대상 자동 등록")).toBeInTheDocument();
    expect(screen.getByText("등록된 스캔 대상 / 발견 엔드포인트 1개")).toBeInTheDocument();
    expect(screen.getByText("핸드셰이크 p95 평균")).toBeInTheDocument();
    expect(screen.getByText("30.2 ms")).toBeInTheDocument();
    expect(screen.getByText("4,216 B")).toBeInTheDocument();
    expect(screen.getByText("web.testbed.local")).toBeInTheDocument();
    expect(screen.getByText("31.4 ms")).toBeInTheDocument();
    expect(screen.getAllByText("12.5 ms").length).toBeGreaterThan(0);
    expect(screen.getAllByText("5.0%").length).toBeGreaterThan(0);
    expect(screen.getByText("자동 등록")).toBeInTheDocument();
    expect(screen.getByText("#31")).toBeInTheDocument();
  });
});
