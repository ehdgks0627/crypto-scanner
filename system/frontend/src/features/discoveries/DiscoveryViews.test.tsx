import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { DiscoveriesView } from "./DiscoveryViews";

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
          cidr: "172.20.5.0/24",
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
          cidr: "172.20.6.0/24",
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

    const discoverySixCheckbox = await screen.findByLabelText("디스커버리 #6 선택");
    expect(discoverySixCheckbox).not.toBeChecked();
    expect(screen.getByText("선택 0개")).toBeInTheDocument();

    await user.click(discoverySixCheckbox);

    expect(discoverySixCheckbox).toBeChecked();
    expect(screen.getByText("선택 1개")).toBeInTheDocument();

    await user.click(discoverySixCheckbox);

    expect(discoverySixCheckbox).not.toBeChecked();
    expect(screen.getByText("선택 0개")).toBeInTheDocument();
  });
});
