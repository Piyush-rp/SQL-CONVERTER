import { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { UserMessage, AssistantMessage } from "@/components/chat/MessageBubble";
import { QueryInput } from "@/components/chat/QueryInput";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { queryService } from "@/services/query";
import type { AskResponse, DatabaseConnection } from "@/types/api";

interface Turn {
  question: string;
  response?: AskResponse;
}

export function ChatWindow({ connection }: { connection: DatabaseConnection | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, isAsking]);

  async function handleSend(question: string) {
    if (!connection) return;
    setTurns((prev) => [...prev, { question }]);
    setIsAsking(true);
    try {
      const response = await queryService.ask(connection.id, question);
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, response } : t)));
    } catch (err) {
      setTurns((prev) =>
        prev.map((t, i) =>
          i === prev.length - 1
            ? {
                ...t,
                response: {
                  status: "failed",
                  question,
                  sql: null,
                  explanation: "",
                  execution: null,
                  chart_spec: null,
                  optimization_suggestions: [],
                  retry_count: 0,
                  error_message: err instanceof Error ? err.message : "Request failed",
                },
              }
            : t
        )
      );
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin px-6 py-6">
        {turns.length === 0 ? (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title={connection ? "Ask anything about this database" : "Select a connection to get started"}
            description={connection ? `Connected to “${connection.name}” - try “how many rows are in each table?”` : undefined}
          />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {turns.map((turn, i) => (
              <div key={i} className="flex flex-col gap-3">
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
        <QueryInput onSend={handleSend} disabled={!connection || isAsking} />
      </div>
    </div>
  );
}
