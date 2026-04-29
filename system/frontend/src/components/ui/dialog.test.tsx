import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "./dialog";

describe("Dialog", () => {
  it("moves focus into the dialog and closes on escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <Dialog open title="Confirm" onClose={onClose}>
        <button type="button">Action</button>
      </Dialog>
    );

    expect(screen.getByRole("button", { name: "닫기" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("keeps reverse tab focus inside the dialog from the initial control", async () => {
    const user = userEvent.setup();

    render(
      <>
        <button type="button">Background</button>
        <Dialog open title="Confirm" onClose={vi.fn()}>
          <button type="button">Action</button>
        </Dialog>
      </>
    );

    await user.keyboard("{Shift>}{Tab}{/Shift}");

    expect(screen.getByRole("button", { name: "Action" })).toHaveFocus();
  });

  it("does not close with escape while close is disabled", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <Dialog open title="Pending" closeDisabled onClose={onClose}>
        <button type="button">Action</button>
      </Dialog>
    );

    await user.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "닫기" })).toBeDisabled();
  });
});
