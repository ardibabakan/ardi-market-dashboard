"use client";

import { useState } from "react";

interface LoginGateProps {
  onSuccess: () => void;
}

export default function LoginGate({ onSuccess }: LoginGateProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(false);

    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        onSuccess();
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="card max-w-sm w-full space-y-4">
        <h1 className="text-xl font-bold text-center">
          Ardi Market Command Center
        </h1>
        <p className="text-txt-secondary text-sm text-center">
          Enter password to access the dashboard
        </p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full px-3 py-2 bg-bg-elevated border border-bg-elevated rounded-lg text-txt text-sm focus:outline-none focus:border-info"
          autoFocus
        />
        {error && (
          <p className="text-loss text-xs text-center">
            Invalid password. Try again.
          </p>
        )}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-2 bg-info rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {loading ? "Authenticating..." : "Enter"}
        </button>
      </form>
    </div>
  );
}
