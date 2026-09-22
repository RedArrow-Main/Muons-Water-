"use client";

import Image from "next/image";
import Link from "next/link";
import { AppIcon } from "@/components/AppShell";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
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

  return <main className="mw-auth"><section className="mw-auth-visual"><Link className="mw-brand" href="/"><span><AppIcon name="leaf"/></span><strong className="text-green-950">MUONS WATER</strong></Link><div><h2>Better water decisions.<br/>From the ground up.</h2><p>Your crop, weather and soil-water estimates in one calm, clear workspace.</p></div><div className="mw-auth-art"><Image src="/images/crop-soil-3d.png" alt="Illustrative maize plant with soil and roots" fill sizes="50vw" priority/></div><p>Science-based estimates. Field-informed decisions.</p></section><section className="mw-auth-form"><div><span className="mw-eyebrow mb-4">WELCOME TO MUONS WATER</span><h1>{mode==='login'?'Welcome back':'Start your growing journey'}</h1><p>{mode==='login'?'Sign in to see your field’s next step.':'Create your account to explore crop and water advisories.'}</p><form onSubmit={handleSubmit}><fieldset className="contents" disabled={!ready || loading}><label className="mw-field">Email<input type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label><label className="mw-field">Password<input type="password" required minLength={8} autoComplete={mode==='login'?'current-password':'new-password'} value={password} onChange={e=>setPassword(e.target.value)} placeholder="At least 8 characters"/></label>{error&&<div role="alert" className="mw-banner warn">{error}</div>}<button className="mw-btn" disabled={loading}>{loading?'Signing in…':mode==='login'?'Sign in':'Create account'}</button></fieldset></form><button className="mt-6 text-sm text-green-800 min-h-[44px]" onClick={()=>{setMode(mode==='login'?'register':'login');setError('');}}>{mode==='login'?'New to MUONS Water? Create an account':'Already have an account? Sign in'}</button><p className="!text-xs !mt-8">Your observations and local browser notes are separate from your account data.</p></div></section></main>;
}
