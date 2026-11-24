import { api, unwrap } from "@/services/api";
import type { AskResponse, QueryHistoryEntry } from "@/types/api";

export const queryService = {
  ask(connectionId: string, question: string, sessionId?: string | null) {
    return unwrap<AskResponse>(
      api.post("/ask", { connection_id: connectionId, question, session_id: sessionId ?? undefined })
    );
  },
  history(limit = 50, offset = 0) {
    return unwrap<QueryHistoryEntry[]>(api.get("/history", { params: { limit, offset } }));
  },
};
