import { describe, expect, it } from "vitest";

import { getIssueById, useWorkspace } from "./store";

const issues = [
  { id: "issue-1" },
  { id: "issue-2" },
] as Parameters<typeof getIssueById>[0];

describe("workspace store", () => {
  it("selects and clears an issue", () => {
    useWorkspace.getState().selectIssue("issue-1");
    expect(useWorkspace.getState().selectedIssueId).toBe("issue-1");

    useWorkspace.getState().selectIssue(null);
    expect(useWorkspace.getState().selectedIssueId).toBeNull();
  });

  it("initializes and navigates sheets", () => {
    useWorkspace.getState().setSheets(["S-101", "S-102", "S-103"]);
    expect(useWorkspace.getState().activeSheet).toBe("S-101");

    useWorkspace.getState().nextSheet();
    expect(useWorkspace.getState().activeSheet).toBe("S-102");

    useWorkspace.getState().previousSheet();
    expect(useWorkspace.getState().activeSheet).toBe("S-101");
  });

  it("updates the active sheet", () => {
    useWorkspace.getState().setSheet("S-102");
    expect(useWorkspace.getState().activeSheet).toBe("S-102");
  });

  it("finds an issue safely", () => {
    expect(getIssueById(issues, "issue-2")?.id).toBe("issue-2");
    expect(getIssueById(issues, "missing")).toBeNull();
    expect(getIssueById(issues, null)).toBeNull();
  });
});
