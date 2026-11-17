"use client";
import { forwardRef } from "react";
import { m, type HTMLMotionProps } from "motion/react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-cobalt text-white border-2 border-cobalt hover:bg-cobalt-deep active:bg-cobalt-deep",
  secondary: "bg-card text-ink border-2 border-ink hover:bg-paper",
  ghost: "bg-transparent text-cobalt border-2 border-transparent hover:bg-cobalt-soft",
  danger: "bg-chili text-white border-2 border-chili",
};

const SIZES: Record<Size, string> = {
  md: "min-h-[44px] px-4 text-base",
  lg: "min-h-[52px] px-5 text-lg",
};

export interface ButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
  children?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, block, className = "", disabled, children, type = "button", ...rest },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <m.button
      ref={ref}
      type={type}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      transition={{ duration: 0.12 }}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`inline-flex select-none items-center justify-center gap-2 rounded-md font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {loading && <Loader2 aria-hidden className="h-5 w-5 motion-safe:animate-spin" />}
      {children}
    </m.button>
  );
});
