import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

import { cn } from "../../lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "icon";

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    size?: ButtonSize;
  }
>;

export function Button({ className, variant = "secondary", size = "md", ...props }: ButtonProps) {
  return <button className={cn("ui-button", `ui-button--${variant}`, `ui-button--${size}`, className)} {...props} />;
}
