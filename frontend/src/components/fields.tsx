import type { InputHTMLAttributes, ReactNode } from "react";
import type { Option } from "../options";
import { Button } from "./Button";

const CONTROL =
  "h-11 w-full rounded-lg border border-line bg-surface px-3 text-body text-ink placeholder:text-[#9aa1ac] " +
  "aria-[invalid=true]:border-danger disabled:bg-neutral/50 disabled:text-muted";

function Description({ id, children }: { id: string; children: ReactNode }) {
  return (
    <p id={id} className="text-body text-muted">
      {children}
    </p>
  );
}

function ErrorText({ id, error }: { id: string; error?: string }) {
  if (!error) return null;
  return (
    <p id={id} role="alert" className="text-small text-danger">
      {error}
    </p>
  );
}

function describedBy(id: string, description?: string, error?: string) {
  return [description ? `${id}-desc` : "", error ? `${id}-err` : ""].filter(Boolean).join(" ") || undefined;
}

interface FieldProps {
  id: string;
  label: string;
  description?: string;
  error?: string;
}

export function TextField({
  id,
  label,
  description,
  error,
  ...input
}: FieldProps & Omit<InputHTMLAttributes<HTMLInputElement>, "id">) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-body">
        {label}
      </label>
      {description && <Description id={`${id}-desc`}>{description}</Description>}
      <input
        id={id}
        className={CONTROL}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, description, error)}
        {...input}
      />
      <ErrorText id={`${id}-err`} error={error} />
    </div>
  );
}

export function SelectField({
  id,
  label,
  description,
  error,
  options,
  value,
  onChange,
}: FieldProps & { options: Option[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-body">
        {label}
      </label>
      {description && <Description id={`${id}-desc`}>{description}</Description>}
      <div className="relative">
        <select
          id={id}
          className={`${CONTROL} appearance-none pr-10`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, description, error)}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </div>
      <ErrorText id={`${id}-err`} error={error} />
    </div>
  );
}

export interface ChoiceOption {
  value: string;
  label: string;
  /** Shown as plain text until picked (the design's "Not sure"). */
  quiet?: boolean;
}

/** A row of buttons where exactly one is picked (yes/no, inches/feet/not sure). */
export function ChoiceGroup({
  id,
  label,
  description,
  error,
  options,
  value,
  onChange,
  inline = false,
}: FieldProps & { options: ChoiceOption[]; value: string; onChange: (value: string) => void; inline?: boolean }) {
  const buttons = (
    <div role="radiogroup" aria-labelledby={`${id}-label`} aria-describedby={describedBy(id, description, error)} className="flex flex-wrap items-center gap-2">
      {options.map((o) => {
        const picked = o.value === value;
        return (
          <Button
            key={o.value}
            size="small"
            role="radio"
            aria-checked={picked}
            variant={picked ? "primary" : o.quiet ? "subtle" : "neutral"}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </Button>
        );
      })}
    </div>
  );
  return (
    <div id={id} tabIndex={-1} className="flex flex-col gap-2 outline-none">
      <div className={inline ? "flex items-center gap-3" : "contents"}>
        <span id={`${id}-label`} className={inline ? "text-small text-muted" : "text-body"}>
          {label}
        </span>
        {inline && buttons}
      </div>
      {description && <Description id={`${id}-desc`}>{description}</Description>}
      {!inline && buttons}
      <ErrorText id={`${id}-err`} error={error} />
    </div>
  );
}
