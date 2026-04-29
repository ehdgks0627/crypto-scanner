import type { HTMLAttributes, PropsWithChildren } from "react";

import { cn } from "../../lib/utils";

type BadgeTone = "neutral" | "green" | "yellow" | "red" | "blue" | "purple";

export function Badge({ className, tone = "neutral", ...props }: PropsWithChildren<HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }>) {
  return <span className={cn("ui-badge", `ui-badge--${tone}`, className)} {...props} />;
}
