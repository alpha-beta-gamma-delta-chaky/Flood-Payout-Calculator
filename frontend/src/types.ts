export type YesNo = "" | "yes" | "no";
export type DepthUnit = "in" | "ft" | "unsure";

/** What the person typed or picked, as text. Turned into an EstimateRequest by validate(). */
export interface Answers {
  flood_zone: string;
  year_built: string;
  floors: string;
  foundation: string;
  basement: string;
  elevated: YesNo;
  primary_residence: YesNo;
  coverage_building: string;
  deductible_building: string;
  depth: string;
  depth_unit: DepthUnit;
}

export const emptyAnswers: Answers = {
  flood_zone: "unknown",
  year_built: "",
  floors: "unknown",
  foundation: "unknown",
  basement: "unknown",
  elevated: "",
  primary_residence: "",
  coverage_building: "",
  deductible_building: "",
  depth: "",
  depth_unit: "in",
};

/** The JSON body of POST /api/estimate. */
export interface EstimateRequest {
  flood_zone: string;
  year_built: number | null;
  floors: string;
  foundation: string;
  basement: string;
  elevated: boolean;
  primary_residence: boolean;
  coverage_building: number;
  deductible_building: number;
  water_depth_inches: number | null; // null = not sure
}

export interface EstimateResponse {
  low: number;
  middle: number;
  high: number;
  coverage_limit: number;
  chance_of_zero: number;
  band_probabilities: Record<string, number>;
  depth_used: boolean;
  model_version: string;
  message: string;
}
