import { usd } from "../format";

interface Props {
  low: number;
  middle: number;
  high: number;
  limit: number;
}

const pct = (v: number, limit: number) => `${Math.min(100, Math.max(0, (v / limit) * 100))}%`;

/** The range on a $0 to coverage-limit scale, with a tick at the middle estimate. */
export function RangeBar({ low, middle, high, limit }: Props) {
  const left = Math.min(100, Math.max(0, (low / limit) * 100));
  const width = Math.max(1.5, Math.min(100, (high / limit) * 100) - left);
  return (
    <div
      role="img"
      aria-label={`Range ${usd(low)} to ${usd(high)} on a scale from $0 to the ${usd(limit)} coverage limit. Middle estimate ${usd(middle)}.`}
      className="flex flex-col gap-1.5"
    >
      <div className="relative h-2 rounded-full bg-line">
        <div className="absolute h-2 rounded-full bg-accent" style={{ left: `${left}%`, width: `${width}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 rounded bg-ink" style={{ left: pct(middle, limit) }} />
      </div>
      <div className="flex justify-between text-small text-muted">
        <span>$0</span>
        <span>Coverage limit {usd(limit)}</span>
      </div>
    </div>
  );
}
