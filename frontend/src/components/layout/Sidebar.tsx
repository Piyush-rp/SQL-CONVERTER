import { useState } from "react";
import { Database, Plus } from "lucide-react";
import { ConnectionListItem } from "@/components/connections/ConnectionListItem";
import { ConnectionForm } from "@/components/connections/ConnectionForm";
import { SchemaBrowser } from "@/components/schema/SchemaBrowser";
import type { ConnectionCreatePayload } from "@/services/connections";
import type { DatabaseConnection, SchemaInfo } from "@/types/api";

export function Sidebar({
  connections,
  activeConnectionId,
  onSelect,
  onCreate,
  schema,
}: {
  connections: DatabaseConnection[];
  activeConnectionId: string | null;
  onSelect: (id: string) => void;
  onCreate: (payload: ConnectionCreatePayload) => Promise<void>;
  schema: SchemaInfo | null;
}) {
  const [showForm, setShowForm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleCreate(payload: ConnectionCreatePayload) {
    setIsSubmitting(true);
    try {
      await onCreate(payload);
      setShowForm(false);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-ink-800 bg-ink-900/40">
      <div className="flex items-center gap-2 px-4 py-3.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/15 text-amber-400">
          <Database className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold text-ink-100">AI SQL Copilot</span>
      </div>

      <div className="flex items-center justify-between px-4 pt-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-ink-500">Connections</span>
        <button onClick={() => setShowForm(true)} className="text-ink-500 hover:text-amber-400" title="Add connection">
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex flex-col gap-0.5 px-2 py-2">
        {connections.length === 0 ? (
          <p className="px-2 py-2 text-xs text-ink-500">No connections yet - add one to get started.</p>
        ) : (
          connections.map((c) => (
            <ConnectionListItem key={c.id} connection={c} isActive={c.id === activeConnectionId} onSelect={() => onSelect(c.id)} />
          ))
        )}
      </div>

      <div className="mt-2 flex-1 overflow-y-auto scrollbar-thin border-t border-ink-800 px-2 py-2">
        <span className="mb-1.5 block px-2 text-[11px] font-medium uppercase tracking-wide text-ink-500">Schema</span>
        <SchemaBrowser schema={schema} />
      </div>

      {showForm && <ConnectionForm onSubmit={handleCreate} onClose={() => setShowForm(false)} isSubmitting={isSubmitting} />}
    </aside>
  );
}
