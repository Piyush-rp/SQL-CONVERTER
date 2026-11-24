import { useMemo, useState, type KeyboardEvent } from "react";
import clsx from "clsx";
import { Database, MessageSquarePlus, Send } from "lucide-react";
import { Button } from "@/components/common/Button";
import type { DatabaseConnection } from "@/types/api";

const ENGINE_LABEL: Record<string, string> = {
  postgresql: "Postgres",
  mysql: "MySQL",
  mssql: "SQL Server",
  sqlite: "SQLite",
};

type Suggestion =
  | { kind: "connection"; connection: DatabaseConnection }
  | { kind: "new" };

/**
 * Finds the connection named right after the "/" - the longest matching name
 * wins, so "/Neon Demo how many orders?" picks "Neon Demo", not "Neon".
 * Returns the connection and whatever text follows its name.
 */
export function parseSlashCommand(value: string, connections: DatabaseConnection[]) {
  if (!value.startsWith("/")) return null;
  const body = value.slice(1);
  const lowered = body.toLowerCase();
  const match = [...connections]
    .sort((a, b) => b.name.length - a.name.length)
    .find((c) => {
      const name = c.name.toLowerCase();
      return lowered.startsWith(name) && (lowered.length === name.length || /\s/.test(lowered[name.length]));
    });
  if (!match) return null;
  return { connection: match, rest: body.slice(match.name.length).trim() };
}

export function QueryInput({
  onSend,
  onSelectConnection,
  onNewChat,
  connections,
  canAsk,
  disabled,
}: {
  onSend: (question: string, connection?: DatabaseConnection) => void;
  onSelectConnection: (id: string) => void;
  onNewChat: () => void;
  connections: DatabaseConnection[];
  canAsk: boolean;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const isCommand = value.startsWith("/");
  const parsed = useMemo(() => parseSlashCommand(value, connections), [value, connections]);

  // Suggestions are shown while the user is still typing the command name.
  const suggestions: Suggestion[] = useMemo(() => {
    if (!isCommand || (parsed && parsed.rest)) return [];
    const typed = value.slice(1).toLowerCase().trim();
    const items: Suggestion[] = connections
      .filter((c) => !typed || c.name.toLowerCase().includes(typed))
      .map((connection) => ({ kind: "connection" as const, connection }));
    if (!typed || "new".startsWith(typed)) items.push({ kind: "new" });
    return items;
  }, [isCommand, parsed, value, connections]);

  function pick(s: Suggestion) {
    setNotice(null);
    if (s.kind === "new") {
      onNewChat();
      setValue("");
      return;
    }
    onSelectConnection(s.connection.id);
    setNotice(`Switched to "${s.connection.name}" - ask your question.`);
    setValue("");
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    setNotice(null);

    if (trimmed.startsWith("/")) {
      if (/^\/new\b/i.test(trimmed) && !parsed) {
        onNewChat();
        setValue("");
        return;
      }
      if (!parsed) {
        setNotice(`No database called "${trimmed.slice(1)}". Type / to see your databases.`);
        return;
      }
      onSelectConnection(parsed.connection.id);
      if (parsed.rest) {
        onSend(parsed.rest, parsed.connection);
      } else {
        setNotice(`Switched to "${parsed.connection.name}" - ask your question.`);
      }
      setValue("");
      return;
    }

    if (!canAsk) {
      setNotice("Select a database first - click one on the left, or type / to pick one.");
      return;
    }
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((h) => (h + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey && !parsed)) {
        e.preventDefault();
        pick(suggestions[Math.min(highlight, suggestions.length - 1)]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setValue("");
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="relative">
      {suggestions.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-xl">
          <p className="border-b border-ink-800 px-3 py-1.5 text-[11px] uppercase tracking-wide text-ink-500">
            Switch database - ↑↓ to move, Enter to pick
          </p>
          <div className="max-h-60 overflow-y-auto py-1">
            {suggestions.map((s, i) => (
              <button
                key={s.kind === "new" ? "__new" : s.connection.id}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(s);
                }}
                onMouseEnter={() => setHighlight(i)}
                className={clsx(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm",
                  i === Math.min(highlight, suggestions.length - 1) ? "bg-ink-800 text-ink-100" : "text-ink-300"
                )}
              >
                {s.kind === "new" ? (
                  <>
                    <MessageSquarePlus className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                    <span className="flex-1 font-mono">/new</span>
                    <span className="text-xs text-ink-500">Start a new chat</span>
                  </>
                ) : (
                  <>
                    <Database className="h-3.5 w-3.5 shrink-0 text-ink-500" />
                    <span className="flex-1 truncate">
                      <span className="font-mono text-ink-500">/</span>
                      {s.connection.name}
                    </span>
                    <span className="text-[10px] uppercase tracking-wide text-ink-500">
                      {ENGINE_LABEL[s.connection.engine] ?? s.connection.engine}
                    </span>
                  </>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-end gap-2 rounded-lg border border-ink-700 bg-ink-900 p-2 focus-within:ring-2 focus-within:ring-amber-400/40">
        <textarea
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setHighlight(0);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your data - or type / to switch database"
          rows={1}
          className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
        />
        <Button onClick={submit} disabled={disabled || !value.trim()} className="shrink-0">
          <Send className="h-3.5 w-3.5" />
          {isCommand && !(parsed && parsed.rest) ? "Go" : "Ask"}
        </Button>
      </div>
      {notice && <p className="mt-1.5 px-1 text-xs text-ink-400">{notice}</p>}
    </div>
  );
}
