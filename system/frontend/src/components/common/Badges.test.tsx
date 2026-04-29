import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithApp } from "../../test/test-utils";
import { RiskTierBadge, StatusBadge } from "./Badges";

describe("badges", () => {
  it("renders risk and status labels", () => {
    renderWithApp(
      <div>
        <RiskTierBadge tier="CRITICAL" />
        <StatusBadge status="RUNNING" />
      </div>
    );

    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });
});
