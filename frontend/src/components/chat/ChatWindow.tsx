import { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { UserMessage, AssistantMessage } from "@/components/chat/MessageBubble";
import { QueryInput } from "@/components/chat/QueryInput";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { queryService } from "@/services/query";
import type { AskResponse, ChatSessionDetail, DatabaseConnection } from "@/types/api";

interface Turn {
  question: string;
  connectionName?: string;
  response?: AskResponse;
}

function failedResponse(question: string, message: string): AskResponse {
  return {
    status: "failed",
    question,
    sql: null,
    explanation: "",
    execution: null,
    chart_spec: null,
    optimization_suggestions: [],
    retry_count: 0,
    error_message: message,
  };
}

/**
 * One chat session. The parent remounts it (via `key`) to start a new chat or
 * open a saved one from the history panel; `initialSession` seeds the turns.
 */
export function ChatWindow({
  connection,
  connections,
  initialSession,
  onSelectConnection,
  onNewChat,
  onSessionSaved,
}: {
  connection: DatabaseConnection | null;
  connections: DatabaseConnection[];
  initialSession: ChatSessionDetail | null;
  onSelectConnection: (id: string) => void;
  onNewChat: () => void;
  onSessionSaved: (sessionId: string) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>(
    () =>
      initialSession?.messages.map((m) => ({
        question: m.question,
        connectionName: m.connection_name,
        response: m.response,
      })) ?? []
  );
  const [sessionId, setSessionId] = useState<string | null>(initialSession?.id ?? null);
  const [isAsking, setIsAsking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, isAsking]);

  async function handleSend(question: string, override?: DatabaseConnection) {
    const target = override ?? connection;
    if (!target) return;
    setTurns((prev) => [...prev, { question, connectionName: target.name }]);
    setIsAsking(true);
    try {
      const response = await queryService.ask(target.id, question, sessionId);
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, response } : t)));
      if (response.session_id) {
        setSessionId(response.session_id);
        onSessionSaved(response.session_id);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setTurns((prev) =>
        prev.map((t, i) => (i === prev.length - 1 ? { ...t, response: failedResponse(question, message) } : t))
      );
    } finally {
      setIsAsking(false);
    }
  }

  // Show which database a question went to when the session used more than one.
  const multipleDatabases = new Set(turns.map((t) => t.connectionName).filter(Boolean)).size > 1;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin px-6 py-6">
        {turns.length === 0 ? (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title={connection ? "Ask anything about this database" : "Select a connection to get started"}
            description={
              connection
                ? `Connected to “${connection.name}” - try “how many rows are in each table?”, or type / to switch database`
                : "Click a database on the left, or type / below to pick one"
            }
          />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {turns.map((turn, i) => (
              <div key={i} className="flex flex-col gap-3">
                {multipleDatabases && turn.connectionName && (
                  <p className="text-right text-[11px] text-ink-500">on {turn.connectionName}</p>
                )}
                <UserMessage question={turn.question} />
                {turn.response ? (
                  <AssistantMessage response={turn.response} />
                ) : (
                  <div className="flex items-center gap-2 rounded-lg rounded-tl-sm border border-ink-800 bg-ink-900/60 px-4 py-3 text-xs text-ink-400">
                    <Spinner className="h-3.5 w-3.5" />
                    Generating SQL and running it...
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mx-auto w-full max-w-3xl px-6 pb-6">
        <QueryInput
          onSend={handleSend}
          onSelectConnection={onSelectConnection}
          onNewChat={onNewChat}
          connections={connections}
          canAsk={!!connection}
          disabled={isAsking}
        />
      </div>
    </div>
  );
}
