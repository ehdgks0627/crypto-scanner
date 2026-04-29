import { AlertTriangle, Loader2 } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../ui/button";

export function LoadingState({ label = "불러오는 중" }: { label?: string }) {
  return (
    <div className="state-view" role="status" aria-live="polite">
      <Loader2 className="spin" size={18} />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError ? error.message : "요청을 처리하지 못했습니다.";
  return (
    <div className="state-view state-view--error" role="alert">
      <AlertTriangle size={18} />
      <span>{message}</span>
      {onRetry ? (
        <Button type="button" size="sm" onClick={onRetry}>
          재시도
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function Section({ children }: PropsWithChildren) {
  return <div className="section-stack">{children}</div>;
}
