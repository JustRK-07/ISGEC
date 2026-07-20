/** Zustand store for the workspace — tracks selected issue + view state. */

import { create } from "zustand";
import type { IssueOut } from "./api";

interface WorkspaceState {
  selectedIssueId: string | null;
  hoveredIssueId: string | null;
  activeSheet: string;
  highlightClash: boolean;

  selectIssue: (id: string | null) => void;
  hoverIssue: (id: string | null) => void;
  setSheet: (sheet: string) => void;
  toggleClashHighlight: () => void;
}

export const useWorkspace = create<WorkspaceState>((set) => ({
  selectedIssueId: null,
  hoveredIssueId: null,
  activeSheet: "0001",
  highlightClash: true,

  selectIssue: (id) => set({ selectedIssueId: id }),
  hoverIssue: (id) => set({ hoveredIssueId: id }),
  setSheet: (sheet) => set({ activeSheet: sheet }),
  toggleClashHighlight: () => set((s) => ({ highlightClash: !s.highlightClash })),
}));

export function getIssueById(issues: IssueOut[], id: string | null): IssueOut | null {
  if (!id) return null;
  return issues.find((it) => it.id === id) ?? null;
}
