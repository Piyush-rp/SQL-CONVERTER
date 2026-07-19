import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Database } from "lucide-react";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Card } from "@/components/common/Card";
import { useAuth } from "@/context/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-500/15 text-amber-400">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-ink-100">AI SQL Copilot</h1>
            <p className="text-xs text-ink-500">Sign in to your workspace</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          <Input label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" isLoading={isLoading} className="mt-1 w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-ink-500">
          No account?{" "}
          <Link to="/register" className="font-medium text-amber-400 hover:text-amber-300">
            Create one
          </Link>
        </p>
      </Card>
    </div>
  );
}
