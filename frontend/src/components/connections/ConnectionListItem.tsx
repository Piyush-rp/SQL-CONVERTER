import { useEffect, useState } from "react";
import clsx from "clsx";
import { CheckCircle2, XCircle, Database as DbIcon } from "lucide-react";
import type { DatabaseConnection } from "@/types/api";
import { connectionsService } from "@/services/connections";

const ENGINE_LABEL: Record<string, string> = {
  postgresql: "Postgres",
  mysql: "MySQL",
  mssql: "SQL Server",
  sqlite: "SQLite",
};

export function ConnectionListItem({
  connection,
  isActive,
  onSelect,
}: {
  connection: DatabaseConnection;
  isActive: boolean;
  onSelect: () => void;
}) {
  const [testResult, setTestResult] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [testMessage, setTestMessage] = useState("");

  async function runTest() {
    setTestResult("testing");
    try {
      const result = await connectionsService.test(connection.id);
      setTestResult(result.success ? "ok" : "fail");
      setTestMessage(result.message);
    } catch (err) {
      setTestResult("fail");
      setTestMessage(err instanceof Error ? err.message : "Connection test failed");
    }
  }

  // Test automatically when the list loads, so the status icon is meaningful
  // right away instead of an empty circle until clicked.
  useEffect(() => {
    runTest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection.id]);

  function handleTest(e: React.MouseEvent) {
    e.stopPropagation();
    runTest();
  }

  const statusTitle =
    testResult === "testing"
      ? "Testing connection..."
      : testResult === "ok"
        ? "Connected - click to test again"
        : testResult === "fail"
          ? `Connection failed: ${testMessage} - click to test again`
          : "Click to test connection";

  return (
    <button
      onClick={onSelect}
      className={clsx(
        "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition-colors",
        isActive ? "bg-ink-800 text-ink-100" : "text-ink-400 hover:bg-ink-850 hover:text-ink-200"
      )}
    >
      <DbIcon className={clsx("h-3.5 w-3.5 shrink-0", isActive ? "text-amber-400" : "text-ink-500")} />
      <span className="flex-1 truncate">{connection.name}</span>
      <span className="shrink-0 text-[10px] uppercase tracking-wide text-ink-500">{ENGINE_LABEL[connection.engine]}</span>
      <button onClick={handleTest} title={statusTitle} className="shrink-0 text-ink-500 hover:text-ink-200">
        {testResult === "testing" && <span className="block h-3 w-3 animate-spin rounded-full border-2 border-ink-500 border-t-amber-400" />}
        {testResult === "ok" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
        {testResult === "fail" && <XCircle className="h-3.5 w-3.5 text-red-400" />}
        {testResult === "idle" && <span className="block h-3 w-3 rounded-full border border-ink-600" />}
      </button>
    </button>
  );
}
