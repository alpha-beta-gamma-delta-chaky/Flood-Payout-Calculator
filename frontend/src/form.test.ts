import { parseNumber, validate } from "./form";
import { emptyAnswers, type Answers } from "./types";

const good: Answers = {
  ...emptyAnswers,
  elevated: "no",
  primary_residence: "yes",
  coverage_building: "250,000",
  deductible_building: "1250",
  depth: "12",
  depth_unit: "in",
};

describe("parseNumber", () => {
  it("accepts commas, dollar signs and spaces", () => {
    expect(parseNumber("250,000")).toBe(250000);
    expect(parseNumber("$1 250")).toBe(1250);
  });
  it("returns null for empty or non-numeric text", () => {
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
  });
});

describe("validate", () => {
  it("builds the request the service expects", () => {
    const { errors, request } = validate(good);
    expect(errors).toEqual({});
    expect(request).toEqual({
      flood_zone: "unknown", year_built: null, floors: "unknown", foundation: "unknown", basement: "unknown",
      elevated: false, primary_residence: true, coverage_building: 250000, deductible_building: 1250,
      water_depth_inches: 12,
    });
    expect(request).not.toHaveProperty("state");
  });

  it("converts feet to inches", () => {
    expect(validate({ ...good, depth: "1.5", depth_unit: "ft" }).request?.water_depth_inches).toBe(18);
  });

  it("sends no depth when the person is not sure", () => {
    expect(validate({ ...good, depth: "", depth_unit: "unsure" }).request?.water_depth_inches).toBeNull();
  });

  it("requires the four required answers", () => {
    const { errors, request } = validate({ ...emptyAnswers, depth_unit: "unsure" });
    expect(request).toBeNull();
    expect(Object.keys(errors).sort()).toEqual(
      ["coverage_building", "deductible_building", "elevated", "primary_residence"].sort(),
    );
  });

  it("requires a depth unless Not sure is chosen", () => {
    expect(validate({ ...good, depth: "" }).errors.depth).toBeDefined();
  });

  it("rejects values outside the allowed ranges", () => {
    expect(validate({ ...good, coverage_building: "900000" }).errors.coverage_building).toBeDefined();
    expect(validate({ ...good, deductible_building: "-5" }).errors.deductible_building).toBeDefined();
    expect(validate({ ...good, depth: "30", depth_unit: "ft" }).errors.depth).toBeDefined();
    expect(validate({ ...good, year_built: "1700" }, 2026).errors.year_built).toBeDefined();
    expect(validate({ ...good, year_built: "2030" }, 2026).errors.year_built).toBeDefined();
  });
});
