"use client";

import { useEffect, ReactNode } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useSession, useProjects, useModals } from "@/lib/store";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const setPendingRedirect = useSession((s) => s.setPendingRedirect);
  const list = useProjects((s) => s.list);
  const fetchList = useProjects((s) => s.fetchList);
  const openUpload = useModals((s) => s.openUpload);

  // Toggle body.signed-in and load projects on mount.
  useEffect(() => {
    document.body.classList.add("signed-in");
    if (list.length === 0) void fetchList();
    return () => {
      document.body.classList.remove("signed-in");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Toggle body[data-view] based on the current pathname. The prototype's
  // CSS gates `.app-dashboard` and `.app-main` visibility on this
  // attribute; the Next.js port relies on routing instead, so we set it
  // here to keep the prototype CSS working.
  useEffect(() => {
    if (pathname.startsWith("/dashboard/") && pathname !== "/dashboard") {
      document.body.dataset.view = "workspace";
    } else if (pathname === "/dashboard") {
      document.body.dataset.view = "dashboard";
    } else {
      delete document.body.dataset.view;
    }
    return () => {
      delete document.body.dataset.view;
    };
  }, [pathname]);

  // Gate: if not signed in, stash the intended destination so the sign-in
  // modal can return the user here after authenticating, then bounce to
  // the landing page. Don't pop the modal — the modal lives globally and
  // would overlap the marketing page. The Nav "Sign in" button opens it
  // explicitly on the landing.
  useEffect(() => {
    if (!user) {
      setPendingRedirect(pathname || "/dashboard");
      router.push("/");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function onSignOut() {
    signOut();
    router.push("/");
  }

  // Don't render the app shell while unauthenticated. The gate effect
  // above bounces to / and stashes the intended destination so the user
  // lands back here after signing in.
  if (!user) return null;

  return (
    <div className="app-shell" id="appShell" aria-hidden="false">
      <header className="app-topbar">
        <div className="app-brand-wrap">
          <span className="app-brand-mark" aria-label="ADV">
            <span className="brand-mark">A</span>
            <span className="brand-name">ADV</span>
          </span>
        </div>
        <div className="app-topbar-right">
          <span className="app-topbar-context">On-prem · local LLM</span>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar" id="appSidebar" aria-label="Primary navigation">
          <nav className="sidebar-section sidebar-primary">
            <Link
              href="/dashboard"
              className={`side-item${pathname === "/dashboard" ? " active" : ""}`}
              title="Projects"
            >
              <span className="side-icon">▦</span>
              <span className="side-label">Projects</span>
            </Link>
            <button type="button" className="side-item" onClick={openUpload} title="New project">
              <span className="side-icon">+</span>
              <span className="side-label">New Project</span>
            </button>
          </nav>

          <div className="sidebar-section sidebar-recent">
            <div className="side-section-label">Recent</div>
            <div className="sidebar-recent-list" id="sidebarRecent">
              {list.slice(0, 6).map((p) => (
                <Link
                  key={p.id}
                  href={`/dashboard/${p.id}`}
                  className={`side-item side-item-recent${pathname === `/dashboard/${p.id}` ? " active" : ""}`}
                  title={p.label}
                >
                  <span className="side-icon">▤</span>
                  <span className="side-label">{p.shortName || p.label}</span>
                </Link>
              ))}
              {list.length === 0 && (
                <div className="side-empty">No projects yet</div>
              )}
            </div>
          </div>

          <div className="sidebar-section sidebar-user">
            <div className="sidebar-user-info">
              <span className="avatar" title={user?.email ?? ""}>
                {user?.initials ?? "?"}
              </span>
              <div className="sidebar-user-meta">
                <span className="sidebar-user-name">{user?.email ?? ""}</span>
                <span className="sidebar-user-role">QA engineer</span>
              </div>
            </div>
            <button type="button" className="side-item side-item-danger" onClick={onSignOut} title="Sign out">
              <span className="side-icon">⏻</span>
              <span className="side-label">Sign out</span>
            </button>
          </div>
        </aside>

        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}
