import { Button } from "../components/Button";
import { Heading, Page } from "../components/Page";
import { RangeBar } from "../components/RangeBar";
import { percent, usd } from "../format";
import { BASEMENTS, FLOORS, FLOOD_ZONES, FOUNDATIONS, labelFor } from "../options";
import type { EstimateRequest, EstimateResponse } from "../types";

interface Props {
  request: EstimateRequest;
  response: EstimateResponse;
  onChange: () => void;
  onStartOver: () => void;
}

const yesNo = (b: boolean) => (b ? "Yes" : "No");
const inches = (n: number) => `${Number.isInteger(n) ? n : n.toFixed(1)} inches`;

export function Result({ request, response, onChange, onStartOver }: Props) {
  const rows: [string, string][] = [
    ["Flood depth", request.water_depth_inches === null ? "Not provided" : inches(request.water_depth_inches)],
    ["Coverage limit", usd(request.coverage_building)],
    ["Deductible", usd(request.deductible_building)],
    ["Flood zone", labelFor(FLOOD_ZONES, request.flood_zone)],
    ["Year built", request.year_built === null ? "Not sure" : String(request.year_built)],
    ["Floors", labelFor(FLOORS, request.floors)],
    ["Foundation", labelFor(FOUNDATIONS, request.foundation)],
    ["Basement", labelFor(BASEMENTS, request.basement)],
    ["Raised building", yesNo(request.elevated)],
    ["Primary residence", yesNo(request.primary_residence)],
  ];
  const bands = Object.entries(response.band_probabilities);

  return (
    <Page>
      <a
        href="#/estimate"
        onClick={(e) => {
          e.preventDefault();
          onChange();
        }}
        className="w-fit text-small text-accent hover:underline"
      >
        ← Change inputs
      </a>
      <Heading title="Estimated payout range" subtitle="Based on past NFIP claims for single-family homes." />

      <section aria-label="Estimate" className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-6">
        <p className="text-[2rem] font-bold leading-[1.2] tracking-[-0.02em] sm:text-title">
          {usd(response.low)} – {usd(response.high)}
        </p>
        <p className="text-body font-semibold">Median estimate: {usd(response.middle)}</p>
        <RangeBar low={response.low} middle={response.middle} high={response.high} limit={response.coverage_limit} />
        <p className="text-small text-muted">
          About half of past claims like yours were paid inside this range. Your policy cannot pay more than{" "}
          {usd(response.coverage_limit)} for the building.
        </p>
        {!response.depth_used && (
          <p className="rounded-lg bg-page p-3 text-small text-muted">
            You did not enter a flood depth, so this range is wider and less precise. Add a depth for a sharper range.
          </p>
        )}

        <hr className="border-line" />
        <p className="text-small text-muted">Chance the building payment is $0</p>
        <p className="text-body font-semibold">{percent(response.chance_of_zero)}</p>

        <hr className="border-line" />
        <p className="text-small text-muted">How past claims like yours were paid</p>
        <ul className="flex flex-col gap-2.5">
          {bands.map(([label, p]) => (
            <li key={label} className="flex flex-col gap-1">
              <div className="flex justify-between text-small">
                <span>{label}</span>
                <span className="font-semibold">{percent(p)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-line">
                <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.round(p * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>

        <hr className="border-line" />
        <p className="text-small text-muted">Based on your answers</p>
        <dl className="flex flex-col gap-2.5 text-body">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-start justify-between gap-4">
              <dt>{k}</dt>
              <dd className="text-right font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="text-small text-muted">This is a range based on past claims, not a promise of payout.</p>
      <div className="flex flex-col gap-3">
        <Button variant="neutral" onClick={onChange}>
          Change inputs
        </Button>
        <Button variant="subtle" onClick={onStartOver}>
          Start over
        </Button>
      </div>
    </Page>
  );
}
