"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const router = useRouter();
  const [str, setStr] = useState<File | null>(null);
  const [mech, setMech] = useState<File | null>(null);
  const [extra, setExtra] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [rev, setRev] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!str || !mech) {
      setError("Both STR and MECH files are required.");
      return;
    }
    setError(null);
    setBusy(true);

    const body = new FormData();
    body.append("str", str);
    body.append("mech", mech);
    if (extra) body.append("extra", extra);
    if (label) body.append("label", label);
    if (rev) body.append("rev", rev);

    try {
      const res = await fetch("/api/projects", { method: "POST", body });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Upload failed (${res.status})`);
      }
      const project = await res.json();
      router.push(`/dashboard/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-h2 font-bold mb-2">New Project</h1>
      <p className="text-text-muted mb-6">
        Upload your Mechanical GA and Structural GA. Optional third file
        (e.g. superimposed reference).
      </p>

      <form onSubmit={submit} className="space-y-4">
        <FileDrop label="Structural GA (required)" file={str} onFile={setStr} accept=".dwg,.dxf,.ifc,.pdf" />
        <FileDrop label="Mechanical GA (required)" file={mech} onFile={setMech} accept=".dwg,.dxf,.ifc,.pdf" />
        <FileDrop label="Superimposed (optional)" file={extra} onFile={setExtra} accept=".dwg,.dxf,.ifc,.pdf" />

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm text-text-muted">Project label</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-border rounded"
              placeholder="TP-104 MECH/STR Review"
            />
          </label>
          <label className="block">
            <span className="text-sm text-text-muted">Revision</span>
            <input
              type="text"
              value={rev}
              onChange={(e) => setRev(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-border rounded"
              placeholder="C"
            />
          </label>
        </div>

        {error && <p className="text-clash-hard text-sm">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full py-3 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-medium rounded"
        >
          {busy ? "Uploading…" : "Upload & Analyze"}
        </button>
      </form>
    </div>
  );
}

function FileDrop({
  label,
  file,
  onFile,
  accept,
}: {
  label: string;
  file: File | null;
  onFile: (f: File | null) => void;
  accept: string;
}) {
  return (
    <label className="block border-2 border-dashed border-border rounded p-4 hover:border-accent transition-colors cursor-pointer">
      <span className="text-sm font-medium block mb-1">{label}</span>
      <span className="text-xs text-text-muted">
        {file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "Click to select"}
      </span>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
