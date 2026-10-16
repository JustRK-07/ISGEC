/** Zustand store — sign-in, projects, modal state. */

import { create } from "zustand";
import { api } from "./api";
import type { IssueOut, ProjectDetail, ProjectSummary } from "./api";

interface SessionState {
  user: { email: string; initials: string } | null;
  signedIn: boolean;
  /** When set, the sign-in modal will redirect here on successful sign-in. */
  pendingRedirect: string | null;
  signIn: (email: string) => void;
  signOut: () => void;
  setPendingRedirect: (path: string | null) => void;
}

interface ProjectsState {
  list: ProjectSummary[];
  active: ProjectDetail | null;
  loading: boolean;
  error: string | null;
  fetchList: () => Promise<void>;
  fetchOne: (id: string) => Promise<ProjectDetail | null>;
  setActive: (p: ProjectDetail | null) => void;
  removeOne: (id: string) => Promise<void>;
  refreshActive: () => Promise<void>;
}

interface ModalState {
  signInOpen: boolean;
  uploadOpen: boolean;
  openSignIn: () => void;
  closeSignIn: () => void;
  openUpload: () => void;
  closeUpload: () => void;
}

interface WorkspaceState {
  selectedIssueId: string | null;
  hoveredIssueId: string | null;
  activeSheet: string | null;
  sheets: string[];
  highlightClash: boolean;
  selectIssue: (id: string | null) => void;
  hoverIssue: (id: string | null) => void;
  setSheet: (sheet: string | null) => void;
  setSheets: (sheets: string[]) => void;
  nextSheet: () => void;
  previousSheet: () => void;
  toggleClashHighlight: () => void;
}

export const useSession = create<SessionState>((set) => ({
  user: null,
  signedIn: false,
  pendingRedirect: null,
  signIn: (email) =>
    set({
      user: { email, initials: initialsOf(email) },
      signedIn: true,
    }),
  signOut: () => set({ user: null, signedIn: false, pendingRedirect: null }),
  setPendingRedirect: (path) => set({ pendingRedirect: path }),
}));

export const useModals = create<ModalState>((set) => ({
  signInOpen: false,
  uploadOpen: false,
  openSignIn: () => set({ signInOpen: true }),
  closeSignIn: () => set({ signInOpen: false }),
  openUpload: () => set({ uploadOpen: true }),
  closeUpload: () => set({ uploadOpen: false }),
}));

export const useProjects = create<ProjectsState>((set, get) => ({
  list: [],
  active: null,
  loading: false,
  error: null,
  fetchList: async () => {
    set({ loading: true, error: null });
    try {
      const list = await api.listProjects();
      set({ list, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },
  fetchOne: async (id) => {
    try {
      const p = await api.getProject(id);
      set({ active: p });
      return p;
    } catch {
      return null;
    }
  },
  setActive: (p) => set({ active: p }),
  removeOne: async (id) => {
    try {
      await api.deleteProject(id);
      set({ list: get().list.filter((p) => p.id !== id) });
      if (get().active?.id === id) set({ active: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
  refreshActive: async () => {
    const cur = get().active;
    if (!cur) return;
    try {
      const p = await api.getProject(cur.id);
      set({ active: p });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
}));

export const useWorkspace = create<WorkspaceState>((set) => ({
  selectedIssueId: null,
  hoveredIssueId: null,
  activeSheet: null,
  sheets: [],
  highlightClash: true,
  selectIssue: (id) => set({ selectedIssueId: id }),
  hoverIssue: (id) => set({ hoveredIssueId: id }),
  setSheet: (sheet) => set({ activeSheet: sheet }),
  setSheets: (sheets) =>
    set((state) => ({
      sheets,
      activeSheet: state.activeSheet && sheets.includes(state.activeSheet)
        ? state.activeSheet
        : (sheets[0] ?? null),
    })),
  nextSheet: () =>
    set((state) => {
      if (!state.sheets.length) return state;
      const index = Math.max(0, state.sheets.indexOf(state.activeSheet ?? ""));
      return { activeSheet: state.sheets[Math.min(state.sheets.length - 1, index + 1)] };
    }),
  previousSheet: () =>
    set((state) => {
      if (!state.sheets.length) return state;
      const index = Math.max(0, state.sheets.indexOf(state.activeSheet ?? ""));
      return { activeSheet: state.sheets[Math.max(0, index - 1)] };
    }),
  toggleClashHighlight: () => set((s) => ({ highlightClash: !s.highlightClash })),
}));

export function getIssueById(issues: IssueOut[], id: string | null): IssueOut | null {
  if (!id) return null;
  return issues.find((it) => it.id === id) ?? null;
}

function initialsOf(email: string): string {
  const local = (email || "").split("@")[0] || "?";
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return local.slice(0, 2).toUpperCase();
}
