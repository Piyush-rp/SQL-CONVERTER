import { type ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  isLoading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary: "bg-amber-500 text-ink-950 hover:bg-amber-400 disabled:bg-amber-500/40",
  secondary: "bg-ink-800 text-ink-100 hover:bg-ink-700 border border-ink-700",
  ghost: "bg-transparent text-ink-300 hover:bg-ink-800 hover:text-ink-100",
  danger: "bg-red-900/40 text-red-300 hover:bg-red-900/60 border border-red-800/60",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", isLoading, className, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || isLoading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium",
        "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60",
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {isLoading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  )
);
Button.displayName = "Button";
