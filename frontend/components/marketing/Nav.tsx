"use client";

import Link from "next/link";
import { useModals, useSession } from "@/lib/store";

export function Nav() {
  const openSignIn = useModals((s) => s.openSignIn);
  const signedIn = useSession((s) => s.signedIn);

  return (
    <nav className="nav" aria-label="Primary">
      <div className="nav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">A</span>
          ADV
        </Link>
        <div className="nav-links">
          <a href="#problem">Problem</a>
          <a href="#architecture">Architecture</a>
          <a href="#capabilities">Capabilities</a>
          <a href="#how">How it works</a>
          <a href="#codes">Standards</a>
          <a href="#faq">FAQ</a>
          {signedIn && (
            <Link href="/dashboard" id="navProjects">Projects</Link>
          )}
        </div>
        <div className="nav-cta">
          {!signedIn && (
            <button type="button" className="btn btn-secondary" onClick={openSignIn}>
              Sign in
            </button>
          )}
          <a href="#cta" className="btn btn-primary">Book a Demo →</a>
        </div>
      </div>
    </nav>
  );
}
