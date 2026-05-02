import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TargetForm } from "./TargetForms";

describe("TargetForm", () => {
  it("locks fields and submit while a mutation is pending", () => {
    render(<TargetForm submitLabel="저장" isSubmitting={true} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("호스트")).toBeDisabled();
    expect(screen.getByLabelText("표시 이름")).toBeDisabled();
    expect(screen.getByRole("button", { name: "저장 중" })).toBeDisabled();
  });

  it("lets users clear the port without coercing it to zero", async () => {
    const user = userEvent.setup();
    render(<TargetForm submitLabel="저장" onSubmit={vi.fn()} />);

    const port = screen.getByLabelText("포트");
    await user.clear(port);

    expect(port).toHaveValue(null);
    expect(screen.getByRole("alert")).toHaveTextContent("포트는 1부터 65535 사이의 정수여야 합니다.");
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });
});
