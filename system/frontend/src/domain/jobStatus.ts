import type { JobStatus, Schema } from "../api/types";

export function isActiveJobStatus(status: JobStatus | undefined | null): boolean {
  return status === "PENDING" || status === "RUNNING";
}

export function isTerminalJobStatus(status: JobStatus | undefined | null): boolean {
  return Boolean(status) && !isActiveJobStatus(status);
}

export function pageHasActiveJob<T extends { status: JobStatus }>(items: T[] | undefined): boolean {
  return (items ?? []).some((item) => isActiveJobStatus(item.status));
}

export function canCancelJob(job: Pick<Schema<"JobEnvelope">, "kind" | "status" | "cancel_requested_at">): boolean {
  if (job.status === "PENDING") {
    return true;
  }
  if (job.status !== "RUNNING" || job.cancel_requested_at) {
    return false;
  }
  return job.kind !== "recompute";
}
