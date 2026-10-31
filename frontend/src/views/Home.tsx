import { Button } from "../components/Button";
import { Page } from "../components/Page";
import { hrefFor, navigate } from "../nav";

export function Home() {
  return (
    <Page>
      <header className="flex items-center justify-between">
        <span className="text-body font-semibold">Flood Payout Calculator</span>
        <a href={hrefFor("how")} className="text-small text-accent hover:underline">
          How it works
        </a>
      </header>
      <section className="flex flex-col gap-4">
        <h1 className="text-[2.25rem] font-bold leading-[1.2] tracking-[-0.02em] sm:text-title">
          Estimate a flood payout range
        </h1>
        <p className="text-body text-muted">
          Built from past NFIP flood insurance claims. Answer ten short questions about your home and policy and see a
          likely range, not a quote.
        </p>
      </section>
      <Button onClick={() => navigate("form")}>Start estimate</Button>
      <p className="text-small text-muted">
        Estimates are not insurance quotes or claim decisions. We do not store personal data.
      </p>
    </Page>
  );
}
