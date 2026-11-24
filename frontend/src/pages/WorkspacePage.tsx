import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { connectionsService } from "@/services/connections";
import type { ConnectionCreatePayload } from "@/services/connections";
import type { DatabaseConnection, SchemaInfo } from "@/types/api";

export function WorkspacePage() {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  const loadConnections = useCallback(async () => {
    const list = await connectionsService.list();
    setConnections(list);
    if (list.length > 0 && !activeId) {
      setActiveId(list[0].id);
    }
  }, [activeId]);

  useEffect(() => {
    loadConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activeId) {
      setSchema(null);
      return;
    }
    setSchemaError(null);
    connectionsService
      .schema(activeId)
      .then(setSchema)
      .catch((err) => {
        setSchema(null);
        setSchemaError(err instanceof Error ? err.message : "Could not load the schema.");
      });
  }, [activeId]);

  async function handleCreate(payload: ConnectionCreatePayload) {
    const created = await connectionsService.create(payload);
    setConnections((prev) => [...prev, created]);
    setActiveId(created.id);
  }

  const activeConnection = connections.find((c) => c.id === activeId) ?? null;

  return (
    <div className="flex h-screen">
      <Sidebar
        connections={connections}
        activeConnectionId={activeId}
        onSelect={setActiveId}
        onCreate={handleCreate}
        schema={schema}
        schemaError={schemaError}
      />
      <div className="flex flex-1 flex-col">
        <TopBar />
        <ChatWindow connection={activeConnection} />
      </div>
    </div>
  );
}
