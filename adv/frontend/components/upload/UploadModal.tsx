"use client";

import { useState, useEffect, useRef, DragEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useModals } from "@/lib/store";

type SlotKey = "str" | "mech" | "extra";

interface SlotFile {
  file: File;
  size: number;
  format: string;
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function detectFormat(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "dwg") return "DWG";
  if (ext === "dxf") return "DXF";
  if (ext === "ifc") return "IFC";
  if (ext === "rvt") return "RVT";
  if (ext === "pdf") return "PDF";
  return ext.toUpperCase() || "UNKNOWN";
}

export function UploadModal() {
  const open = useModals((s) => s.uploadOpen);
  const close = useModals((s) => s.closeUpload);
  const router = useRouter();

  const [slots, setSlots] = useState<Record<SlotKey, SlotFile | null>>({
    str: null,
    mech: null,
    extra: null,
  });
  const [projectLabel, setProjectLabel] = useState("");
  const [revision, setRevision] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const strInputRef = useRef<HTMLInputElement>(null);
  const mechInputRef = useRef<HTMLInputElement>(null);
  const extraInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setSlots({ str: null, mech: null, extra: null });
      setProjectLabel("");
      setRevision("");
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

  function setSlot(key: SlotKey, file: File | null) {
    setSlots((s) => ({ ...s, [key]: file ? { file, size: file.size, format: detectFormat(file.name) } : null }));
  }

  function onDrop(e: DragEvent, key: SlotKey) {
    e.preventDefault();
    e.stopPropagation();
    const f = e.dataTransfer.files?.[0];
    if (f) setSlot(key, f);
  }

  function onPick(e: ChangeEvent<HTMLInputElement>, key: SlotKey) {
    const f = e.target.files?.[0];
    if (f) setSlot(key, f);
    e.target.value = "";
  }

  async function onSubmit() {
    if (!slots.str || !slots.mech) return;
    if (!projectLabel.trim()) {
      setError("Project label is required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("label", projectLabel.trim());
      if (revision) fd.append("rev", revision);
      fd.append("str", slots.str.file);
      fd.append("mech", slots.mech.file);
      if (slots.extra) fd.append("extra", slots.extra.file);
      const created = await api.createProject(fd);
      close();
      router.push(`/dashboard/${created.id}`);
    } catch (e) {
      setError((e as Error).message || "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !!slots.str && !!slots.mech && !!projectLabel.trim() && !submitting;

  return (
    <div
      className={`upload-modal${open ? " open" : ""}`}
      id="uploadModal"
      aria-hidden={!open}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="upload-card" role="dialog" aria-labelledby="uploadTitle" aria-describedby="uploadSub">
        <button className="upload-close" type="button" aria-label="Close upload dialog" onClick={close}>×</button>

        <div className="upload-eyebrow">[ NEW QA/QC CHECK · ON-PREM · LOCAL LLM ]</div>
        <h2 id="uploadTitle">Upload Mechanical &amp; Structural GAs.</h2>
        <p className="upload-sub" id="uploadSub">
          Both drawings must share a common grid. We never send data off your hardware —
          validation runs locally behind a self-hosted LLM.
        </p>

        <div className="upload-grid">
          <Slot
            disc="str"
            label="STRUCTURAL DWG"
            file={slots.str}
            onDrop={onDrop}
            onPick={onPick}
            onRemove={() => setSlot("str", null)}
            inputRef={strInputRef}
          />
          <Slot
            disc="mech"
            label="MECHANICAL DWG"
            file={slots.mech}
            onDrop={onDrop}
            onPick={onPick}
            onRemove={() => setSlot("mech", null)}
            inputRef={mechInputRef}
          />
        </div>

        <details className="upload-extra">
          <summary>Add a third reference drawing (Architectural / Plumbing / PDF)</summary>
          <div className="upload-extra-body">
            <Slot
              disc="extra"
              label="REFERENCE DRAWING"
              file={slots.extra}
              onDrop={onDrop}
              onPick={onPick}
              onRemove={() => setSlot("extra", null)}
              inputRef={extraInputRef}
              optional
            />
          </div>
        </details>

        <div className="upload-meta">
          <div className="upload-field">
            <label htmlFor="uploadProjectLabel">Project label</label>
            <input
              type="text"
              id="uploadProjectLabel"
              placeholder="e.g. Finchley Rd · Level 03 · QA-Q4"
              value={projectLabel}
              onChange={(e) => setProjectLabel(e.target.value)}
            />
          </div>
          <div className="upload-field">
            <label htmlFor="uploadRevision">Revision</label>
            <select id="uploadRevision" value={revision} onChange={(e) => setRevision(e.target.value)}>
              <option value="">—</option>
              <option value="C">C (current)</option>
              <option value="B">B</option>
              <option value="A">A</option>
            </select>
          </div>
        </div>

        {error && <div className="upload-error" role="alert">{error}</div>}

        <div className="upload-actions">
          <button type="button" className="upload-cancel" onClick={close} disabled={submitting}>Cancel</button>
          <button type="button" className="upload-submit" onClick={onSubmit} disabled={!canSubmit}>
            {submitting ? "Uploading…" : "Run QA/QC Check →"}
          </button>
        </div>
      </div>
    </div>
  );
}

interface SlotProps {
  disc: SlotKey;
  label: string;
  file: SlotFile | null;
  onDrop: (e: DragEvent, key: SlotKey) => void;
  onPick: (e: ChangeEvent<HTMLInputElement>, key: SlotKey) => void;
  onRemove: () => void;
  inputRef: React.RefObject<HTMLInputElement>;
  optional?: boolean;
}

function Slot({ disc, label, file, onDrop, onPick, onRemove, inputRef, optional }: SlotProps) {
  const tag = disc.toUpperCase();
  return (
    <div className={`upload-slot upload-slot-${disc}`} data-discipline={disc}>
      <label className="upload-slot-label" htmlFor={`uploadInput${tag}`}>
        <span className="upload-slot-icon">{tag}</span>
        {label} <em>({optional ? "optional" : "required"})</em>
      </label>
      <div
        className="upload-drop"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => onDrop(e, disc)}
        onClick={() => !file && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          id={`uploadInput${tag}`}
          accept={disc === "extra" ? ".dwg,.dxf,.ifc,.pdf" : ".dwg,.dxf,.ifc"}
          hidden
          onChange={(e) => onPick(e, disc)}
        />
        {!file && (
          <div className="upload-empty">
            <div className="upload-arrow">⬇</div>
            <div><strong>Drop file here</strong> or click to browse</div>
            <div className="upload-formats">
              {disc === "extra" ? ".dwg · .dxf · .ifc · .pdf — ≤ 500 MB" : ".dwg · .dxf · .ifc — ≤ 500 MB"}
            </div>
          </div>
        )}
        {file && (
          <div className="upload-file-card">
            <button className="upload-file-remove" type="button" onClick={(e) => { e.stopPropagation(); onRemove(); }} title="Remove file" aria-label="Remove file">×</button>
            <div className="upload-file-name">{file.file.name}</div>
            <div className="upload-file-meta">
              <span>{formatBytes(file.size)}</span> · <span>{file.format}</span>
            </div>
          </div>
        )}
      </div>
      <div className="upload-status" data-status={file ? "ok" : ""}>
        <span className="dot"></span>
        <span className="upload-status-text">
          {file ? "Ready" : optional ? "Optional — skip if not needed" : "Awaiting file"}
        </span>
      </div>
    </div>
  );
}
