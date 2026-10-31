import type { EstimateRequest, EstimateResponse } from "./types";

export type ApiErrorKind = "invalid" | "rate-limit" | "server" | "network";

export class ApiError extends Error {
  kind: ApiErrorKind;
  /** Field name -> message, when the service rejected specific fields (kind "invalid"). */
  fieldErrors: Record<string, string>;

  constructor(kind: ApiErrorKind, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.kind = kind;
    this.fieldErrors = fieldErrors;
  }
}

export async function requestEstimate(body: EstimateRequest, signal?: AbortSignal): Promise<EstimateResponse> {
  let res: Response;
  try {
    res = await fetch("/api/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("network", "We could not reach the service. Check your connection and try again.");
  }

  if (res.ok) return (await res.json()) as EstimateResponse;

  if (res.status === 422) {
    const fieldErrors: Record<string, string> = {};
    try {
      const data = (await res.json()) as { detail?: { loc?: (string | number)[]; msg?: string }[] };
      for (const d of data.detail ?? []) {
        const field = String(d.loc?.[d.loc.length - 1] ?? "");
        if (field) fieldErrors[field] = d.msg ?? "Invalid value.";
      }
    } catch {
      /* fall through with no field details */
    }
    throw new ApiError("invalid", "Some answers were not accepted. Check the highlighted fields.", fieldErrors);
  }
  if (res.status === 429) throw new ApiError("rate-limit", "Too many requests. Wait a minute and try again.");
  throw new ApiError("server", "Something went wrong on our side. Please try again.");
}
