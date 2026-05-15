import { formatDistanceToNowStrict } from "date-fns";
import { ko } from "date-fns/locale";

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

export function formatRelative(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return `${formatDistanceToNowStrict(new Date(value), { addSuffix: true, locale: ko })}`;
}

export function formatNumber(value?: number | null): string {
  return new Intl.NumberFormat("ko-KR").format(value ?? 0);
}

export function formatScore(value?: number | null): string {
  return (value ?? 0).toFixed(1);
}

export function formatOptionalScore(value?: number | null): string {
  return value == null ? "-" : value.toFixed(1);
}
