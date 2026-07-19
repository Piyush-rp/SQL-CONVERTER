import type { ReactNode } from "react";

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-ink-700 py-12 px-6 text-center">
      {icon && <div className="text-ink-500">{icon}</div>}
      <div>
        <p className="text-sm font-medium text-ink-200">{title}</p>
        {description && <p className="mt-1 text-xs text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}
