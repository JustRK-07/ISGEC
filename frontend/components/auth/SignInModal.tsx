"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useModals, useSession } from "@/lib/store";

export function SignInModal() {
  const open = useModals((s) => s.signInOpen);
  const close = useModals((s) => s.closeSignIn);
  const signIn = useSession((s) => s.signIn);
  const pendingRedirect = useSession((s) => s.pendingRedirect);
  const setPendingRedirect = useSession((s) => s.setPendingRedirect);
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState("engineer@firm.com");
  const [password, setPassword] = useState("reviewer");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setError("");
      setSubmitting(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email.trim()) {
      setError("Enter your work email.");
      return;
    }
    if (password.length < 4) {
      setError("Password must be at least 4 characters.");
      return;
    }
    setSubmitting(true);
    // Demo mode: any non-empty email + 4+ char password succeeds.
    signIn(email.trim());

    // Honor the destination the AppShell stashed before bouncing to "/"
    // (or fall back to the current pathname). If neither makes sense for
    // an authenticated user, send them to the dashboard.
    const target =
      pendingRedirect && pendingRedirect !== "/" && pendingRedirect !== "/upload"
        ? pendingRedirect
        : pathname === "/" || pathname === "/upload"
        ? "/dashboard"
        : pathname;

    setPendingRedirect(null);
    close();
    setSubmitting(false);
    router.push(target);
  }

  return (
    <div
      className={`auth-modal${open ? " open" : ""}`}
      id="authModal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="authTitle"
      aria-hidden={!open}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="auth-card">
        <button className="auth-close" type="button" aria-label="Close sign in" onClick={close}>×</button>
        <div className="auth-brand">
          <span className="brand-mark">A</span>
          ADV
        </div>
        <div className="auth-eyebrow">[ QA/QC · DWG-NATIVE · ON-PREM ]</div>
        <h2 id="authTitle">Sign in to your workspace.</h2>
        <p className="auth-sub">
          Engineer-grade validation on every drawing set — sheet-located, grid-anchored, formula-grounded.
        </p>

        <form id="authForm" autoComplete="off" noValidate onSubmit={onSubmit}>
          <div className="auth-field">
            <label htmlFor="authEmail">Work email</label>
            <input
              type="email"
              id="authEmail"
              name="email"
              placeholder="engineer@firm.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="auth-field">
            <label htmlFor="authPass">Password</label>
            <input
              type="password"
              id="authPass"
              name="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
            Sign in &amp; open dashboard →
          </button>
        </form>

        <div className="auth-hint">
          <strong>Demo mode:</strong> any non-empty email + password (min 4 chars) signs you in. Use the sign-out chip in the top-right to return to the marketing site.
        </div>
      </div>
    </div>
  );
}
