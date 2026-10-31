import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { BackLink, Heading, Page } from "../components/Page";
import { navigate } from "../nav";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-body font-semibold">{title}</h2>
      <div className="flex flex-col gap-2 text-body text-muted">{children}</div>
    </section>
  );
}

export function HowItWorks() {
  return (
    <Page>
      <BackLink to="home">Home</BackLink>
      <Heading title="How it works" subtitle="What the numbers are, and what they are not." />

      <Section title="Where the numbers come from">
        <p>
          The calculator compares your answers with 774,990 past claims for single-family homes insured by the National
          Flood Insurance Program (NFIP), from FEMA's public OpenFEMA data, for losses from 2010 to 2024.
        </p>
      </Section>

      <Section title="What the range means">
        <p>
          The range covers the middle half of what similar claims were paid for the building: about a quarter were paid
          less than the low end and about a quarter more than the high end. The median estimate is the middle point.
          Your coverage limit is the most the policy can pay for the building.
        </p>
      </Section>

      <Section title="What matters most">
        <p>
          The depth of water inside the building matters most, followed by your building coverage, basement type,
          foundation type and year built. If you do not know the depth, the calculator uses a separate version without
          it, and the range is wider and less reliable.
        </p>
      </Section>

      <Section title="How accurate it is">
        <p>
          On floods the model had not seen, about half (50%) of real building payouts landed inside the range. On
          claims from 2025, which were held back until the end, it was 44%. Whole floods can be paid well above or
          below similar homes elsewhere, and the largest payouts are sometimes missed.
        </p>
      </Section>

      <Section title="What it cannot do">
        <p>
          It is not an insurance quote or a claim decision: the adjuster decides the payment. It covers insured
          single-family homes only, not condominiums, businesses or contents, and only claims that were filed are in
          the data.
        </p>
      </Section>

      <Section title="Your privacy">
        <p>We do not store your answers. Only anonymous request counts are logged.</p>
      </Section>

      <Button onClick={() => navigate("form")}>Start estimate</Button>
    </Page>
  );
}
