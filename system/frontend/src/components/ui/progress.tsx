export function Progress({ value }: { value: number }) {
  const clampedValue = Math.max(0, Math.min(100, value));
  return (
    <div
      className="ui-progress"
      role="progressbar"
      aria-label={`진행률 ${clampedValue}%`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clampedValue}
    >
      <span style={{ width: `${clampedValue}%` }} />
    </div>
  );
}
