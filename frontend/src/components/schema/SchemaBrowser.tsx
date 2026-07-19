import { useState } from "react";
import { ChevronRight, KeyRound, Link2, Table2 } from "lucide-react";
import clsx from "clsx";
import type { SchemaInfo, TableInfo } from "@/types/api";

function TableNode({ table }: { table: TableInfo }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-left text-xs text-ink-300 hover:bg-ink-850"
      >
        <ChevronRight className={clsx("h-3 w-3 shrink-0 text-ink-500 transition-transform", open && "rotate-90")} />
        <Table2 className="h-3 w-3 shrink-0 text-ink-500" />
        <span className="truncate font-mono">{table.name}</span>
        <span className="ml-auto shrink-0 text-[10px] text-ink-600">{table.columns.length}</span>
      </button>
      {open && (
        <div className="ml-6 flex flex-col gap-0.5 border-l border-ink-800 pl-2 py-1">
          {table.columns.map((col) => (
            <div key={col.name} className="flex items-center gap-1.5 py-0.5 text-[11px] text-ink-400">
              {col.isPrimaryKey ? (
                <KeyRound className="h-2.5 w-2.5 shrink-0 text-amber-400" />
              ) : table.foreignKeys.some((fk) => fk.column === col.name) ? (
                <Link2 className="h-2.5 w-2.5 shrink-0 text-ink-500" />
              ) : (
                <span className="w-2.5 shrink-0" />
              )}
              <span className="font-mono text-ink-300">{col.name}</span>
              <span className="ml-auto shrink-0 text-ink-600">{col.type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SchemaBrowser({ schema }: { schema: SchemaInfo | null }) {
  if (!schema) {
    return <p className="px-2 py-3 text-xs text-ink-500">Select a connection to browse its schema.</p>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      {schema.tables.map((table) => (
        <TableNode key={table.name} table={table} />
      ))}
    </div>
  );
}
