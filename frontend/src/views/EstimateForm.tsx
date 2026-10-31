import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, requestEstimate } from "../api";
import { Button } from "../components/Button";
import { ChoiceGroup, SelectField, TextField } from "../components/fields";
import { BackLink, Heading, Page } from "../components/Page";
import { validate, type Errors } from "../form";
import { BASEMENTS, FLOORS, FLOOD_ZONES, FOUNDATIONS } from "../options";
import type { Answers, DepthUnit, EstimateRequest, EstimateResponse, YesNo } from "../types";

interface Props {
  answers: Answers;
  onAnswers: (a: Answers) => void;
  onDone: (request: EstimateRequest, response: EstimateResponse) => void;
}

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "error"; error: ApiError };

const YES_NO = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];
const UNITS = [
  { value: "in", label: "Inches" },
  { value: "ft", label: "Feet" },
  { value: "unsure", label: "Not sure", quiet: true },
];

/** The service names the depth field differently from the form. */
const FIELD_FOR_SERVER: Record<string, keyof Answers> = { water_depth_inches: "depth" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="text-body font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function EstimateForm({ answers, onAnswers, onDone }: Props) {
  const [errors, setErrors] = useState<Errors>({});
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const lastRequest = useRef<EstimateRequest | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const set = <K extends keyof Answers>(key: K, value: Answers[K]) => {
    onAnswers({ ...answers, [key]: value });
    if (errors[key]) setErrors({ ...errors, [key]: undefined });
  };

  async function send(request: EstimateRequest) {
    lastRequest.current = request;
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setStatus({ kind: "loading" });
    try {
      const response = await requestEstimate(request, ctrl.signal);
      onDone(request, response);
    } catch (e) {
      if (ctrl.signal.aborted) return;
      const error = e instanceof ApiError ? e : new ApiError("server", "Something went wrong. Please try again.");
      if (error.kind === "invalid") {
        const fromServer: Errors = {};
        for (const [field, msg] of Object.entries(error.fieldErrors)) {
          fromServer[FIELD_FOR_SERVER[field] ?? (field as keyof Answers)] = msg;
        }
        setErrors(fromServer);
      }
      setStatus({ kind: "error", error });
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const { errors: found, request } = validate(answers);
    setErrors(found);
    if (!request) {
      const first = Object.keys(found)[0];
      document.getElementById(`f-${first}`)?.focus();
      return;
    }
    void send(request);
  }

  const loading = status.kind === "loading";

  return (
    <Page>
      <BackLink to="home">Home</BackLink>
      <Heading title="Your home" subtitle="Ten questions. Takes about a minute." />

      <form onSubmit={submit} noValidate className="flex flex-col gap-8">
        <Section title="The building">
          <SelectField id="f-flood_zone" label="Flood zone" description="Shown on your flood insurance declarations page."
            options={FLOOD_ZONES} value={answers.flood_zone} onChange={(v) => set("flood_zone", v)} error={errors.flood_zone} />
          <TextField id="f-year_built" label="Year built (optional)" placeholder="e.g. 1985" inputMode="numeric"
            value={answers.year_built} onChange={(e) => set("year_built", e.target.value)} error={errors.year_built} />
          <SelectField id="f-floors" label="Number of floors" options={FLOORS} value={answers.floors}
            onChange={(v) => set("floors", v)} error={errors.floors} />
          <SelectField id="f-foundation" label="Foundation type" options={FOUNDATIONS} value={answers.foundation}
            onChange={(v) => set("foundation", v)} error={errors.foundation} />
          <SelectField id="f-basement" label="Basement type" options={BASEMENTS} value={answers.basement}
            onChange={(v) => set("basement", v)} error={errors.basement} />
          <ChoiceGroup id="f-elevated" label="Is the building raised above the ground?"
            description="For example, on posts, piers or piles." options={YES_NO} value={answers.elevated}
            onChange={(v) => set("elevated", v as YesNo)} error={errors.elevated} />
          <ChoiceGroup id="f-primary_residence" label="Is it your primary residence?" options={YES_NO}
            value={answers.primary_residence} onChange={(v) => set("primary_residence", v as YesNo)}
            error={errors.primary_residence} />
        </Section>

        <Section title="Your policy">
          <TextField id="f-coverage_building" label="Building coverage limit (USD)" placeholder="e.g. 250,000"
            inputMode="numeric" value={answers.coverage_building}
            onChange={(e) => set("coverage_building", e.target.value)} error={errors.coverage_building} />
          <TextField id="f-deductible_building" label="Building deductible (USD)" placeholder="e.g. 1,250"
            inputMode="numeric" value={answers.deductible_building}
            onChange={(e) => set("deductible_building", e.target.value)} error={errors.deductible_building} />
        </Section>

        <Section title="The flood">
          <TextField id="f-depth" label="Flood depth inside the building"
            description="Depth of water inside the building, above the floor." placeholder="Enter a number"
            inputMode="decimal" value={answers.depth} disabled={answers.depth_unit === "unsure"}
            onChange={(e) => set("depth", e.target.value)} error={errors.depth} />
          <ChoiceGroup id="f-depth_unit" label="Unit" inline options={UNITS} value={answers.depth_unit}
            onChange={(v) => set("depth_unit", v as DepthUnit)} />
        </Section>

        {status.kind === "error" && (
          <div role="alert" className="flex flex-col gap-3 rounded-xl border border-danger bg-danger-soft p-4">
            <p className="text-body text-danger">{status.error.message}</p>
            {status.error.kind !== "invalid" && lastRequest.current && (
              <Button variant="neutral" size="small" className="self-start"
                onClick={() => void send(lastRequest.current as EstimateRequest)}>
                Try again
              </Button>
            )}
          </div>
        )}

        <Button type="submit" disabled={loading}>
          {loading ? "Estimating…" : "See estimate"}
        </Button>
      </form>
    </Page>
  );
}
