import { api, unwrap } from "@/services/api";
import type { ChatSessionDetail, ChatSessionSummary } from "@/types/api";

export const sessionsService = {
  list() {
    return unwrap<ChatSessionSummary[]>(api.get("/sessions"));
  },
  get(id: string) {
    return unwrap<ChatSessionDetail>(api.get(`/sessions/${id}`));
  },
  update(id: string, changes: { bookmarked?: boolean; title?: string }) {
    return unwrap<ChatSessionSummary>(api.patch(`/sessions/${id}`, changes));
  },
  async remove(id: string) {
    await api.delete(`/sessions/${id}`);
  },
};
