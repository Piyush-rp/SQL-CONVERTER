import { useState, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/common/Button";

export function QueryInput({ onSend, disabled }: { onSend: (question: string) => void; disabled: boolean }) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex items-end gap-2 rounded-lg border border-ink-700 bg-ink-900 p-2 focus-within:ring-2 focus-within:ring-amber-400/40">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about your data - e.g. “total revenue by month this year”"
        rows={1}
        className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
      />
      <Button onClick={submit} disabled={disabled || !value.trim()} className="shrink-0">
        <Send className="h-3.5 w-3.5" />
        Ask
      </Button>
    </div>
  );
}
