import type { HTMLAttributes } from "react";
import clsx from "clsx";

export function Card({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx("rounded-lg border border-ink-800 bg-ink-900/60 backdrop-blur-sm", className)}
      {...props}
    >
      {children}
    </div>
  );
}
