import type { ReactNode } from "react";
import { hrefFor, type Route } from "../nav";

export function Page({ children }: { children: ReactNode }) {
  return <main className="mx-auto flex w-full max-w-[560px] flex-col gap-8 px-4 py-12 sm:py-24">{children}</main>;
}

export function BackLink({ to, children }: { to: Route; children: ReactNode }) {
  return (
    <a href={hrefFor(to)} className="w-fit text-small text-accent hover:underline">
      ← {children}
    </a>
  );
}

export function Heading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-heading font-semibold">{title}</h1>
      {subtitle && <p className="text-body text-muted">{subtitle}</p>}
    </div>
  );
}
