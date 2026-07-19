import { AlertTriangle, Info, User } from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { SQLBlock } from "@/components/chat/SQLBlock";
import { ResultsTable } from "@/components/chat/ResultsTable";
import { ChartRenderer } from "@/components/charts/ChartRenderer";
import type { AskResponse } from "@/types/api";

const STATUS_BADGE: Record<AskResponse["status"], { tone: "success" | "warning" | "danger"; label: string }> = {
  success: { tone: "success", label: "Success" },
  failed: { tone: "danger", label: "Failed" },
  rejected: { tone: "danger", label: "Blocked" },
  clarification_needed: { tone: "warning", label: "Needs clarification" },
};

export function UserMessage({ question }: { question: string }) {
  return (
    <div className="flex items-start justify-end gap-2.5">
      <div className="max-w-2xl rounded-lg rounded-tr-sm bg-ink-800 px-4 py-2.5 text-sm text-ink-100">{question}</div>
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-700 text-ink-300">
        <User className="h-3.5 w-3.5" />
      </div>
    </div>
  );
}

export function AssistantMessage({ response }: { response: AskResponse }) {
  const badge = STATUS_BADGE[response.status];

  if (response.status !== "success") {
    return (
      <div className="max-w-2xl rounded-lg rounded-tl-sm border border-ink-800 bg-ink-900/60 px-4 py-3">
        <div className="mb-1.5 flex items-center gap-2">
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </div>
        <p className="text-sm text-ink-300">{response.error_message}</p>
        {response.sql && (
          <div className="mt-3">
            <SQLBlock sql={response.sql} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-3 rounded-lg rounded-tl-sm border border-ink-800 bg-ink-900/60 px-4 py-3.5">
      <div className="flex items-center gap-2">
        <Badge tone={badge.tone}>{badge.label}</Badge>
        {response.retry_count > 0 && (
          <span className="text-[11px] text-ink-500">self-corrected after {response.retry_count} retry</span>
        )}
      </div>

      {response.explanation && <p className="text-sm text-ink-200">{response.explanation}</p>}

      {response.sql && <SQLBlock sql={response.sql} />}

      {response.chart_spec && response.execution && response.chart_spec.chart_type !== "table" && response.chart_spec.chart_type !== "none" && (
        <ChartRenderer chartSpec={response.chart_spec} execution={response.execution} />
      )}

      {response.execution && <ResultsTable execution={response.execution} />}

      {response.optimization_suggestions.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-md border border-ink-800 bg-ink-950/40 px-3 py-2">
          {response.optimization_suggestions.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-ink-400">
              {s.severity === "warning" ? (
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
              ) : (
                <Info className="mt-0.5 h-3 w-3 shrink-0 text-ink-500" />
              )}
              <span>{s.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
