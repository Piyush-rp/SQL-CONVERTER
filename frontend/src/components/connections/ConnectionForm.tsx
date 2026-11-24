import { useState, type FormEvent } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import type { DBEngine } from "@/types/api";
import type { ConnectionCreatePayload } from "@/services/connections";

const ENGINE_DEFAULTS: Record<DBEngine, { port: number; label: string }> = {
  postgresql: { port: 5432, label: "PostgreSQL" },
  mysql: { port: 3306, label: "MySQL" },
  mssql: { port: 1433, label: "SQL Server" },
  sqlite: { port: 0, label: "SQLite" },
};

export function ConnectionForm({
  onSubmit,
  onClose,
  isSubmitting,
}: {
  onSubmit: (payload: ConnectionCreatePayload) => Promise<void>;
  onClose: () => void;
  isSubmitting: boolean;
}) {
  const [engine, setEngine] = useState<DBEngine>("postgresql");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState(ENGINE_DEFAULTS.postgresql.port);
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [filePath, setFilePath] = useState("");
  const [readOnly, setReadOnly] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isSqlite = engine === "sqlite";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await onSubmit({
        name,
        engine,
        host,
        port,
        database,
        username,
        password,
        file_path: filePath,
        read_only: readOnly,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create connection");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-lg border border-ink-800 bg-ink-900 p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-100">New database connection</h2>
          <button onClick={onClose} className="text-ink-500 hover:text-ink-200">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          <Input label="Connection name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Production analytics DB" />

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-ink-400">Engine</label>
            <select
              value={engine}
              onChange={(e) => {
                const next = e.target.value as DBEngine;
                setEngine(next);
                setPort(ENGINE_DEFAULTS[next].port);
              }}
              className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 focus:outline-none focus:ring-2 focus:ring-amber-400/50"
            >
              {(Object.keys(ENGINE_DEFAULTS) as DBEngine[]).map((key) => (
                <option key={key} value={key}>
                  {ENGINE_DEFAULTS[key].label}
                </option>
              ))}
            </select>
          </div>

          {isSqlite ? (
            <Input
              label="File path"
              required
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="/data/mydb.sqlite"
            />
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Input
                    label="Host"
                    required
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    placeholder="db.example.com or tunnel host"
                  />
                </div>
                <Input label="Port" type="number" required value={port} onChange={(e) => setPort(Number(e.target.value))} />
              </div>
              <p className="-mt-1.5 text-xs text-ink-500">
                The server must reach this host. For a database on your own computer, expose it with a TCP tunnel
                (e.g. ngrok, pinggy) and enter the tunnel's host and port - "localhost" refers to the server, not your PC.
              </p>
              <Input label="Database name" required value={database} onChange={(e) => setDatabase(e.target.value)} />
              <div className="grid grid-cols-2 gap-3">
                <Input label="Username" required value={username} onChange={(e) => setUsername(e.target.value)} />
                <Input label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
            </>
          )}

          <label className="flex items-center gap-2 text-sm text-ink-300">
            <input type="checkbox" checked={readOnly} onChange={(e) => setReadOnly(e.target.checked)} className="rounded border-ink-600 bg-ink-800" />
            Read-only (recommended - blocks INSERT/UPDATE/DELETE)
          </label>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              Connect
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
