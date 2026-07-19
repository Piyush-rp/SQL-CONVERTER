import clsx from "clsx";

type Tone = "success" | "warning" | "danger" | "neutral";

const toneClasses: Record<Tone, string> = {
  success: "bg-emerald-900/40 text-emerald-300 border-emerald-800/60",
  warning: "bg-amber-900/30 text-amber-300 border-amber-700/50",
  danger: "bg-red-900/40 text-red-300 border-red-800/60",
  neutral: "bg-ink-800 text-ink-300 border-ink-700",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", toneClasses[tone])}>
      {children}
    </span>
  );
}
