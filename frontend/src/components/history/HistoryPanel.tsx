import { useState } from "react";
import clsx from "clsx";
import { History, MessageSquarePlus, Star, Trash2 } from "lucide-react";
import type { ChatSessionSummary } from "@/types/api";

function timeAgo(iso: string) {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function SessionItem({
  session,
  isActive,
  onOpen,
  onToggleBookmark,
  onDelete,
}: {
  session: ChatSessionSummary;
  isActive: boolean;
  onOpen: () => void;
  onToggleBookmark: () => void;
  onDelete: () => void;
}) {
  // Two-click delete instead of a browser confirm() dialog.
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      onMouseLeave={() => setConfirmDelete(false)}
      className={clsx(
        "group flex cursor-pointer items-start gap-2 rounded-md px-2.5 py-2 text-left",
        isActive ? "bg-ink-800" : "hover:bg-ink-850"
      )}
    >
      <div className="min-w-0 flex-1">
        <p className={clsx("truncate text-sm", isActive ? "text-ink-100" : "text-ink-300")}>{session.title}</p>
        <p className="truncate text-[11px] text-ink-500">
          {session.connection_name || "No database"} · {session.message_count}{" "}
          {session.message_count === 1 ? "question" : "questions"} · {timeAgo(session.updated_at)}
        </p>
      </div>
      <button
        type="button"
        title={session.bookmarked ? "Remove bookmark" : "Bookmark this session"}
        onClick={(e) => {
          e.stopPropagation();
          onToggleBookmark();
        }}
        className={clsx(
          "mt-0.5 shrink-0",
          session.bookmarked ? "text-amber-400" : "text-ink-600 opacity-0 group-hover:opacity-100 hover:text-amber-400"
        )}
      >
        <Star className="h-3.5 w-3.5" fill={session.bookmarked ? "currentColor" : "none"} />
      </button>
      <button
        type="button"
        title={confirmDelete ? "Click again to delete" : "Delete session"}
        onClick={(e) => {
          e.stopPropagation();
          if (confirmDelete) onDelete();
          else setConfirmDelete(true);
        }}
        className={clsx(
          "mt-0.5 shrink-0",
          confirmDelete ? "text-red-400" : "text-ink-600 opacity-0 group-hover:opacity-100 hover:text-red-400"
        )}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function HistoryPanel({
  sessions,
  activeSessionId,
  onOpen,
  onNewChat,
  onToggleBookmark,
  onDelete,
}: {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onOpen: (id: string) => void;
  onNewChat: () => void;
  onToggleBookmark: (session: ChatSessionSummary) => void;
  onDelete: (id: string) => void;
}) {
  const bookmarked = sessions.filter((s) => s.bookmarked);
  const recent = sessions.filter((s) => !s.bookmarked);

  function renderList(list: ChatSessionSummary[]) {
    return list.map((s) => (
      <SessionItem
        key={s.id}
        session={s}
        isActive={s.id === activeSessionId}
        onOpen={() => onOpen(s.id)}
        onToggleBookmark={() => onToggleBookmark(s)}
        onDelete={() => onDelete(s.id)}
      />
    ));
  }

  return (
    <aside className="hidden h-full w-72 shrink-0 flex-col border-l border-ink-800 bg-ink-900/40 lg:flex">
      <div className="flex items-center justify-between px-4 py-3.5">
        <span className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <History className="h-4 w-4 text-ink-400" />
          History
        </span>
        <button
          type="button"
          onClick={onNewChat}
          title="Start a new chat"
          className="flex items-center gap-1.5 rounded-md border border-ink-700 px-2 py-1 text-xs text-ink-300 hover:border-amber-500/50 hover:text-amber-400"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-4">
        {sessions.length === 0 ? (
          <p className="px-2 py-2 text-xs text-ink-500">
            Your chats appear here. Ask a question to start one, then ★ to bookmark it.
          </p>
        ) : (
          <>
            {bookmarked.length > 0 && (
              <div className="mb-3">
                <span className="mb-1 block px-2 text-[11px] font-medium uppercase tracking-wide text-ink-500">
                  Bookmarked
                </span>
                {renderList(bookmarked)}
              </div>
            )}
            {recent.length > 0 && (
              <div>
                <span className="mb-1 block px-2 text-[11px] font-medium uppercase tracking-wide text-ink-500">Recent</span>
                {renderList(recent)}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
