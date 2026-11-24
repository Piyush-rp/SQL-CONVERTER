import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { HistoryPanel } from "@/components/history/HistoryPanel";
import { connectionsService } from "@/services/connections";
import type { ConnectionCreatePayload } from "@/services/connections";
import { sessionsService } from "@/services/sessions";
import type { ChatSessionDetail, ChatSessionSummary, DatabaseConnection, SchemaInfo } from "@/types/api";

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

  // --- chat sessions (history panel) -------------------------------------------
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [openedSession, setOpenedSession] = useState<ChatSessionDetail | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0); // remounts ChatWindow for a new/opened session

  const loadSessions = useCallback(() => {
    sessionsService.list().then(setSessions).catch(() => undefined);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  function startNewChat() {
    setOpenedSession(null);
    setActiveSessionId(null);
    setChatKey((k) => k + 1);
  }

  async function openSession(id: string) {
    try {
      const detail = await sessionsService.get(id);
      if (detail.connection_id && connections.some((c) => c.id === detail.connection_id)) {
        setActiveId(detail.connection_id);
      }
      setOpenedSession(detail);
      setActiveSessionId(detail.id);
      setChatKey((k) => k + 1);
    } catch {
      loadSessions(); // it may have been deleted elsewhere
    }
  }

  async function toggleBookmark(session: ChatSessionSummary) {
    const next = !session.bookmarked;
    setSessions((prev) => prev.map((s) => (s.id === session.id ? { ...s, bookmarked: next } : s)));
    try {
      await sessionsService.update(session.id, { bookmarked: next });
    } catch {
      loadSessions();
    }
  }

  async function deleteSession(id: string) {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (id === activeSessionId) startNewChat();
    try {
      await sessionsService.remove(id);
    } catch {
      loadSessions();
    }
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
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <ChatWindow
          key={chatKey}
          connection={activeConnection}
          connections={connections}
          initialSession={openedSession}
          onSelectConnection={setActiveId}
          onNewChat={startNewChat}
          onSessionSaved={(id) => {
            setActiveSessionId(id);
            loadSessions();
          }}
        />
      </div>
      <HistoryPanel
        sessions={sessions}
        activeSessionId={activeSessionId}
        onOpen={openSession}
        onNewChat={startNewChat}
        onToggleBookmark={toggleBookmark}
        onDelete={deleteSession}
      />
    </div>
  );
}
