import type { Answers, EstimateRequest } from "./types";

export type Errors = Partial<Record<keyof Answers, string>>;

// Same limits as the service (app/schema.py reads them from the model code); the service has the final say.
export const LIMITS = {
  coverage: { min: 1_000, max: 250_000 },
  deductible: { min: 0, max: 50_000 },
  yearMin: 1800,
  depthInches: { min: 0, max: 240 },
};

/** "250,000", "$250 000" and "250000" all give 250000. Empty or not a number gives null. */
export function parseNumber(text: string): number | null {
  const cleaned = text.replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

const usdText = (n: number) => "$" + n.toLocaleString("en-US");

export function validate(
  a: Answers,
  thisYear: number = new Date().getFullYear(),
): { errors: Errors; request: EstimateRequest | null } {
  const errors: Errors = {};

  if (a.elevated === "") errors.elevated = "Choose yes or no.";
  if (a.primary_residence === "") errors.primary_residence = "Choose yes or no.";

  const coverage = parseNumber(a.coverage_building);
  if (coverage === null) errors.coverage_building = "Enter your building coverage limit.";
  else if (coverage < LIMITS.coverage.min || coverage > LIMITS.coverage.max)
    errors.coverage_building = `Enter an amount from ${usdText(LIMITS.coverage.min)} to ${usdText(LIMITS.coverage.max)}.`;

  const deductible = parseNumber(a.deductible_building);
  if (deductible === null) errors.deductible_building = "Enter your building deductible (0 if none).";
  else if (deductible < LIMITS.deductible.min || deductible > LIMITS.deductible.max)
    errors.deductible_building = `Enter an amount from ${usdText(LIMITS.deductible.min)} to ${usdText(LIMITS.deductible.max)}.`;

  let year: number | null = null;
  if (a.year_built.trim() !== "") {
    const y = parseNumber(a.year_built);
    if (y === null || !Number.isInteger(y) || y < LIMITS.yearMin || y > thisYear)
      errors.year_built = `Enter a year from ${LIMITS.yearMin} to ${thisYear}, or leave it empty.`;
    else year = y;
  }

  let depthInches: number | null = null;
  if (a.depth_unit !== "unsure") {
    const d = parseNumber(a.depth);
    const factor = a.depth_unit === "ft" ? 12 : 1;
    if (d === null) errors.depth = "Enter a depth, or choose Not sure.";
    else if (d < 0 || d * factor > LIMITS.depthInches.max)
      errors.depth =
        a.depth_unit === "ft" ? "Enter a depth from 0 to 20 feet." : `Enter a depth from 0 to ${LIMITS.depthInches.max} inches.`;
    else depthInches = Math.round(d * factor * 10) / 10;
  }

  if (Object.keys(errors).length > 0) return { errors, request: null };

  return {
    errors,
    request: {
      flood_zone: a.flood_zone,
      year_built: year,
      floors: a.floors,
      foundation: a.foundation,
      basement: a.basement,
      elevated: a.elevated === "yes",
      primary_residence: a.primary_residence === "yes",
      coverage_building: coverage as number,
      deductible_building: deductible as number,
      water_depth_inches: depthInches,
    },
  };
}
