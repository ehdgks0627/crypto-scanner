import type { ReactNode } from "react";

import { Card } from "../ui/card";

export function MetricCard({ label, value, meta, onClick }: { label: string; value: ReactNode; meta?: ReactNode; onClick?: () => void }) {
  const content = (
    <>
      <span className="metric-card__label">{label}</span>
      <strong>{value}</strong>
      {meta ? <span className="metric-card__meta">{meta}</span> : null}
    </>
  );
  if (onClick) {
    return (
      <button type="button" className="metric-card metric-card--button" onClick={onClick}>
        {content}
      </button>
    );
  }
  return <Card className="metric-card">{content}</Card>;
}
