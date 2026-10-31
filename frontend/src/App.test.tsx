import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import type { EstimateResponse } from "./types";

const RESPONSE: EstimateResponse = {
  low: 38600, middle: 88500, high: 138600, coverage_limit: 250000, chance_of_zero: 0.009,
  band_probabilities: { $0: 0.009, "under $10k": 0.105, "$10–50k": 0.165, "$50–100k": 0.374, "over $100k": 0.346 },
  depth_used: true, model_version: "2.0.0", message: "",
};

const ok = () => Promise.resolve(new Response(JSON.stringify(RESPONSE), { status: 200 }));

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Start estimate" }));
  const elevated = screen.getByRole("radiogroup", { name: /raised above the ground/i });
  await user.click(within(elevated).getByRole("radio", { name: "No" }));
  const primary = screen.getByRole("radiogroup", { name: /primary residence/i });
  await user.click(within(primary).getByRole("radio", { name: "Yes" }));
  await user.type(screen.getByLabelText(/building coverage limit/i), "250,000");
  await user.type(screen.getByLabelText(/building deductible/i), "1250");
  await user.type(screen.getByLabelText(/flood depth inside/i), "12");
  await user.click(screen.getByRole("button", { name: "See estimate" }));
}

beforeEach(() => {
  window.location.hash = "";
});
afterEach(() => vi.unstubAllGlobals());

describe("app flow", () => {
  it("home -> form -> result, sending the homeowner's answers without a state", async () => {
    const fetchMock = vi.fn(ok);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await fillAndSubmit(user);

    expect(await screen.findByText("$38,600 – $138,600")).toBeInTheDocument();
    expect(screen.getByText("Median estimate: $88,500")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/estimate");
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ coverage_building: 250000, deductible_building: 1250, water_depth_inches: 12,
      elevated: false, primary_residence: true });
    expect(body).not.toHaveProperty("state");
  });

  it("shows field errors and does not call the service when answers are missing", async () => {
    const fetchMock = vi.fn(ok);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Start estimate" }));
    await user.click(screen.getByRole("button", { name: "See estimate" }));
    expect(await screen.findByText("Enter your building coverage limit.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an error with Try again, which resends the same request", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockImplementation(ok);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach the service/i);

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("$38,600 – $138,600")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]?.body).toBe(fetchMock.mock.calls[0][1]?.body);
  });

  it("Change inputs keeps the answers; Start over clears them", async () => {
    vi.stubGlobal("fetch", vi.fn(ok));
    const user = userEvent.setup();
    render(<App />);
    await fillAndSubmit(user);
    await screen.findByText("$38,600 – $138,600");

    await user.click(screen.getByRole("button", { name: "Change inputs" }));
    expect(await screen.findByLabelText(/building coverage limit/i)).toHaveValue("250,000");

    await user.click(screen.getByRole("button", { name: "See estimate" }));
    await screen.findByText("$38,600 – $138,600");
    await user.click(screen.getByRole("button", { name: "Start over" }));
    expect(await screen.findByRole("heading", { name: "Estimate a flood payout range" })).toBeInTheDocument();
    await waitFor(() => expect(window.location.hash).toBe("#/"));
  });

  it("opens How it works from the home page", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("link", { name: "How it works" }));
    expect(await screen.findByRole("heading", { name: "How it works" })).toBeInTheDocument();
  });
});
