import { api, unwrap } from "@/services/api";
import type { AskResponse, QueryHistoryEntry } from "@/types/api";

export const queryService = {
  ask(connectionId: string, question: string, llmProvider?: string) {
    return unwrap<AskResponse>(
      api.post("/ask", { connection_id: connectionId, question, llm_provider: llmProvider })
    );
  },
  history(limit = 50, offset = 0) {
    return unwrap<QueryHistoryEntry[]>(api.get("/history", { params: { limit, offset } }));
  },
};
