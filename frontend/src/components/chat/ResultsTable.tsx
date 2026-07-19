import type { ExecutionResult } from "@/types/api";

export function ResultsTable({ execution }: { execution: ExecutionResult }) {
  if (execution.rows.length === 0) {
    return <p className="px-3 py-4 text-xs text-ink-500">Query ran successfully but returned no rows.</p>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-ink-800">
      <div className="max-h-80 overflow-auto scrollbar-thin">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-ink-850">
            <tr>
              {execution.columns.map((col) => (
                <th key={col} className="border-b border-ink-800 px-3 py-2 font-medium text-ink-400">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {execution.rows.map((row, i) => (
              <tr key={i} className="odd:bg-ink-900/40 hover:bg-ink-800/60">
                {row.map((cell, j) => (
                  <td key={j} className="border-b border-ink-850 px-3 py-1.5 font-mono text-ink-200">
                    {cell === null ? <span className="text-ink-600 italic">null</span> : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-ink-800 bg-ink-900/60 px-3 py-1.5 text-[11px] text-ink-500">
        <span>
          {execution.row_count} row{execution.row_count === 1 ? "" : "s"}
          {execution.truncated && " (truncated)"}
        </span>
        <span>{execution.execution_time_ms}ms</span>
      </div>
    </div>
  );
}
