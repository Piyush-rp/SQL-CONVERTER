export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-ink-500 border-t-amber-400 ${className}`} />;
}
