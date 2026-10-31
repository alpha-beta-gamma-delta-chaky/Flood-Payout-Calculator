import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "neutral" | "subtle";
type Size = "medium" | "small";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-white border border-primary hover:bg-ink",
  neutral: "bg-neutral text-ink border border-neutral-line hover:bg-[#d6d6d6]",
  subtle: "bg-transparent text-ink border border-transparent hover:bg-black/5",
};

const SIZES: Record<Size, string> = {
  medium: "h-11 w-full px-4 text-body",
  small: "h-8 px-3 text-small",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "primary", size = "medium", className = "", ...rest }: Props) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center rounded-lg font-normal transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    />
  );
}
