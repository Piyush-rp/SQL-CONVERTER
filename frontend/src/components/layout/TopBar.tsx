import { LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export function TopBar() {
  const { user, logout } = useAuth();
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-ink-800 bg-ink-900/80 px-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-emerald-400" />
        <span className="text-xs text-ink-400">Connected</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-ink-400">{user?.email}</span>
        <button onClick={logout} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-ink-400 hover:bg-ink-800 hover:text-ink-200">
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </header>
  );
}
