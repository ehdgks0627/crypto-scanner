import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError } from "../../api/client";
import { ErrorState, LoadingState } from "./StateViews";

describe("StateViews", () => {
  it("announces loading states", () => {
    render(<LoadingState label="Loading data" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading data");
  });

  it("announces error states", () => {
    render(<ErrorState error={new ApiError("Broken", { status: 500 })} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Broken");
  });
});
