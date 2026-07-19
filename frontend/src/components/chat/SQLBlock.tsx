import { useState } from "react";
import { Check, Copy } from "lucide-react";

export function SQLBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="relative rounded-lg border border-ink-800 bg-ink-950">
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 rounded p-1.5 text-ink-500 hover:bg-ink-800 hover:text-ink-200"
        title="Copy SQL"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      <pre className="overflow-x-auto px-4 py-3 pr-10 font-mono text-[13px] leading-relaxed text-amber-200/90">
        {sql}
      </pre>
    </div>
  );
}
