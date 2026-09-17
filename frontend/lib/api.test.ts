import { describe, expect, it } from "vitest";

import { extractDetail } from "./api";

describe("extractDetail", () => {
  it("reads FastAPI string details", () => {
    expect(extractDetail({ detail: "Project not found" })).toBe("Project not found");
  });

  it("formats FastAPI validation details", () => {
    expect(
      extractDetail({ detail: [{ loc: ["body", "state"], msg: "Invalid state" }] }),
    ).toBe("body.state: Invalid state");
  });

  it("falls back to legacy error fields", () => {
    expect(extractDetail({ error: "Conversion failed" })).toBe("Conversion failed");
  });
});
