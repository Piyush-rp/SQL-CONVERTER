import { useState, type FormEvent } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import type { DBEngine } from "@/types/api";
import type { ConnectionCreatePayload } from "@/services/connections";

const ENGINE_DEFAULTS: Record<DBEngine, { port: number; label: string; extraPlaceholder: string }> = {
  postgresql: { port: 5432, label: "PostgreSQL", extraPlaceholder: "e.g. sslmode=require" },
  mysql: { port: 3306, label: "MySQL", extraPlaceholder: "e.g. ssl=true" },
  mssql: { port: 1433, label: "SQL Server", extraPlaceholder: "e.g. tds_version=7.4" },
  sqlite: { port: 0, label: "SQLite", extraPlaceholder: "" },
};

const SCHEME_TO_ENGINE: Record<string, DBEngine> = {
  postgres: "postgresql",
  postgresql: "postgresql",
  mysql: "mysql",
  mariadb: "mysql",
  mssql: "mssql",
  sqlserver: "mssql",
  sqlite: "sqlite",
};

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/**
 * Parses connection URLs as cloud providers show them, e.g.
 *   postgresql://user:p@ss@host:5432/db?sslmode=require
 *   mysql://user:pass@host:3306/db,  jdbc:sqlserver://host:1433/db
 * Splits credentials at the LAST "@" so unescaped "@" in passwords still works.
 */
export function parseConnectionUrl(input: string) {
  const raw = input.trim().replace(/^jdbc:/i, "");
  const match = raw.match(/^([a-z0-9+.-]+):\/\/(.*)$/i);
  if (!match) return null;
  const engine = SCHEME_TO_ENGINE[match[1].toLowerCase().split("+")[0]];
  if (!engine) return null;

  let rest = match[2];
  let query = "";
  const q = rest.indexOf("?");
  if (q >= 0) {
    query = rest.slice(q + 1);
    rest = rest.slice(0, q);
  }
  if (engine === "sqlite") {
    return { engine, filePath: safeDecode(rest.startsWith("/") ? rest : `/${rest}`) };
  }

  let username = "";
  let password = "";
  const at = rest.lastIndexOf("@");
  if (at >= 0) {
    const creds = rest.slice(0, at);
    rest = rest.slice(at + 1);
    const colon = creds.indexOf(":");
    username = safeDecode(colon >= 0 ? creds.slice(0, colon) : creds);
    password = safeDecode(colon >= 0 ? creds.slice(colon + 1) : "");
  }
  const slash = rest.indexOf("/");
  const hostPort = slash >= 0 ? rest.slice(0, slash) : rest;
  const database = slash >= 0 ? safeDecode(rest.slice(slash + 1)) : "";
  const portMatch = hostPort.match(/^(.*):(\d+)$/);
  const host = portMatch ? portMatch[1] : hostPort;
  const port = portMatch ? Number(portMatch[2]) : ENGINE_DEFAULTS[engine].port;

  return { engine, host, port, database, username, password, extraParams: query };
}

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
  const [connectionUrl, setConnectionUrl] = useState("");
  const [urlNote, setUrlNote] = useState<string | null>(null);
  const [host, setHost] = useState("");
  const [port, setPort] = useState(ENGINE_DEFAULTS.postgresql.port);
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [filePath, setFilePath] = useState("");
  const [extraParams, setExtraParams] = useState("");
  const [readOnly, setReadOnly] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isSqlite = engine === "sqlite";

  function applyConnectionUrl(value: string) {
    setConnectionUrl(value);
    if (!value.trim()) {
      setUrlNote(null);
      return;
    }
    const parsed = parseConnectionUrl(value);
    if (!parsed) {
      setUrlNote("Couldn't read that URL - it should look like postgresql://user:password@host:5432/database");
      return;
    }
    setEngine(parsed.engine);
    if ("filePath" in parsed) {
      setFilePath(parsed.filePath ?? "");
    } else {
      setHost(parsed.host);
      setPort(parsed.port);
      setDatabase(parsed.database);
      setUsername(parsed.username);
      setPassword(parsed.password);
      setExtraParams(parsed.extraParams);
    }
    if (!name.trim()) setName(`${ENGINE_DEFAULTS[parsed.engine].label} database`);
    setUrlNote("Filled in the fields below from the URL - check them and click Connect.");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        engine,
        host: host.trim(),
        port,
        database: database.trim(),
        username: username.trim(),
        password,
        file_path: filePath.trim(),
        extra_params: extraParams.trim(),
        read_only: readOnly,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create connection");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="max-h-[92vh] w-full max-w-md overflow-y-auto rounded-lg border border-ink-800 bg-ink-900 p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-100">New database connection</h2>
          <button onClick={onClose} className="text-ink-500 hover:text-ink-200">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          <div className="flex flex-col gap-1">
            <Input
              label="Paste a connection URL (optional)"
              value={connectionUrl}
              onChange={(e) => applyConnectionUrl(e.target.value)}
              placeholder="postgresql://user:password@host:5432/dbname"
              autoComplete="off"
              spellCheck={false}
            />
            {urlNote && <p className="text-xs text-ink-500">{urlNote}</p>}
          </div>

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
              placeholder="/var/task/demo_store.sqlite"
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
                <Input
                  label="Username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                />
                <Input
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="blank if none"
                  autoComplete="new-password"
                />
              </div>
              <div className="flex flex-col gap-1">
                <Input
                  label="Extra options (optional)"
                  value={extraParams}
                  onChange={(e) => setExtraParams(e.target.value)}
                  placeholder={ENGINE_DEFAULTS[engine].extraPlaceholder}
                  autoComplete="off"
                  spellCheck={false}
                />
                <p className="text-xs text-ink-500">
                  Usually not needed - SSL is used automatically when the server supports it. Add options here only if
                  your provider asks for them.
                </p>
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
