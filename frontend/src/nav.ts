export type Route = "home" | "form" | "result" | "how";

const HASHES: Record<Route, string> = { home: "#/", form: "#/estimate", result: "#/result", how: "#/how-it-works" };

export function routeFromHash(hash: string): Route {
  const found = (Object.keys(HASHES) as Route[]).find((r) => HASHES[r] === hash);
  return found ?? "home";
}

export function navigate(route: Route): void {
  window.location.hash = HASHES[route];
}

export function hrefFor(route: Route): string {
  return HASHES[route];
}
