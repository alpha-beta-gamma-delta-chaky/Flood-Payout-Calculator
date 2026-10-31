import { percent, usd } from "./format";

describe("format", () => {
  it("formats dollars with thousands separators", () => {
    expect(usd(38600)).toBe("$38,600");
    expect(usd(250000.4)).toBe("$250,000");
  });
  it("formats small chances without showing 0%", () => {
    expect(percent(0.009)).toBe("1%");
    expect(percent(0.001)).toBe("<1%");
    expect(percent(0)).toBe("0%");
    expect(percent(0.346)).toBe("35%");
  });
});
