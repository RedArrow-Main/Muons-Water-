"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Email and password are required");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      if (mode === "register") {
        await register(email, password);
      }
      await login(email, password);
      router.push("/dashboard");
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-mono text-2xl font-bold text-green-800 tracking-wide">MUONS WATER</h1>
          <p className="font-mono text-sm text-gray-500 mt-1 tracking-wider">
            FURROWCAST ADVISORY LOGIN
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4"
        >
          <div>
            <label className="block font-mono text-xs uppercase tracking-wider text-gray-500 mb-1">
              Email
            </label>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full min-h-[44px] rounded-lg border border-gray-300 px-4 py-2 text-sm font-mono focus:outline-none focus:border-green-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block font-mono text-xs uppercase tracking-wider text-gray-500 mb-1">
              Password
            </label>
            <input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full min-h-[44px] rounded-lg border border-gray-300 px-4 py-2 text-sm font-mono focus:outline-none focus:border-green-500"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="font-mono text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full min-h-[44px] bg-green-600 text-white font-mono text-sm rounded-lg hover:bg-green-700 disabled:opacity-60 transition-colors"
          >
            {loading
              ? "WORKING…"
              : mode === "login"
              ? "LOG IN"
              : "CREATE ACCOUNT & LOG IN"}
          </button>
        </form>

        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
          className="w-full mt-4 text-center font-mono text-xs text-gray-500 hover:text-green-700"
        >
          {mode === "login"
            ? "No account? Create one"
            : "Have an account? Log in"}
        </button>
      </div>
    </main>
  );
}
