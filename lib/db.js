// lib/db.js — SQLite init + schema migrations + helpers
'use strict';

const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');

const DATA_DIR = process.env.DATA_DIR || './data';
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
const dbPath = path.join(DATA_DIR, 'adv.db');
const db = new Database(dbPath);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS projects (
    id           TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    short_name   TEXT NOT NULL,
    rev          TEXT,
    kind         TEXT NOT NULL DEFAULT 'Str + Mech',
    status       TEXT NOT NULL,                -- 'processing' | 'ready' | 'error'
    created_at   INTEGER NOT NULL,
    last_opened  INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS files (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    discipline   TEXT NOT NULL,                -- 'str' | 'mech' | 'extra'
    filename     TEXT NOT NULL,
    format       TEXT NOT NULL,                -- 'dwg' | 'dxf' | 'ifc' | 'pdf'
    size_bytes   INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    stored_path  TEXT NOT NULL,
    parse_meta   TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    parse_error  TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_files_proj ON files(project_id);

  CREATE TABLE IF NOT EXISTS entities (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    discipline   TEXT NOT NULL,
    sheet        TEXT NOT NULL DEFAULT 'default',
    kind         TEXT NOT NULL,
    label        TEXT,
    x_mm         REAL, y_mm REAL,
    w_mm         REAL, h_mm REAL,
    rotation     REAL,
    meta         TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_entities_proj ON entities(project_id);

  CREATE TABLE IF NOT EXISTS issues (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    severity     TEXT NOT NULL,                -- 'high' | 'medium' | 'low' | 'pass'
    category     TEXT NOT NULL,
    code         TEXT NOT NULL,
    title        TEXT NOT NULL,
    evidence     TEXT,
    sheet        TEXT,
    grid         TEXT,
    mech_ref     TEXT,
    str_ref      TEXT,
    formula      TEXT,
    result_json  TEXT,
    state        TEXT NOT NULL DEFAULT 'open',
    assigned     TEXT,
    created_at   INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_issues_proj ON issues(project_id);
`);

// ---- prepared statements ----
const stmts = {
  insertProject: db.prepare(`
    INSERT INTO projects (id, label, short_name, rev, kind, status, created_at, last_opened)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `),
  getProject: db.prepare(`SELECT * FROM projects WHERE id = ?`),
  listProjects: db.prepare(`SELECT * FROM projects ORDER BY last_opened DESC`),
  touchProject: db.prepare(`UPDATE projects SET last_opened = ? WHERE id = ?`),
  updateProjectStatus: db.prepare(`UPDATE projects SET status = ? WHERE id = ?`),
  deleteProject: db.prepare(`DELETE FROM projects WHERE id = ?`),

  insertFile: db.prepare(`
    INSERT INTO files (id, project_id, discipline, filename, format, size_bytes, sha256, stored_path, parse_meta, parse_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `),
  getFilesForProject: db.prepare(`SELECT * FROM files WHERE project_id = ? ORDER BY discipline`),
  updateFileParse: db.prepare(`UPDATE files SET parse_meta = ?, parse_status = ?, parse_error = ? WHERE id = ?`),

  insertEntitiesBatch: db.prepare(`
    INSERT INTO entities (id, project_id, discipline, sheet, kind, label, x_mm, y_mm, w_mm, h_mm, rotation, meta)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `),
  getEntitiesForProject: db.prepare(`SELECT * FROM entities WHERE project_id = ? ORDER BY discipline, kind`),

  insertIssue: db.prepare(`
    INSERT INTO issues (id, project_id, severity, category, code, title, evidence, sheet, grid, mech_ref, str_ref, formula, result_json, state, assigned, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `),
  getIssuesForProject: db.prepare(`SELECT * FROM issues WHERE project_id = ? ORDER BY
    CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
    created_at DESC`),
  clearIssuesForProject: db.prepare(`DELETE FROM issues WHERE project_id = ?`),
};

// ---- helper wrappers ----
function insertProject(p) {
  return stmts.insertProject.run(
    p.id, p.label, p.shortName, p.rev || '', p.kind || 'Str + Mech',
    p.status || 'processing', p.createdAt, p.lastOpened
  );
}
function listProjects() {
  return stmts.listProjects.all().map(rowToProject);
}
function getProject(id) {
  const row = stmts.getProject.get(id);
  return row ? rowToProject(row) : null;
}
function touchProject(id) {
  stmts.touchProject.run(Date.now(), id);
}
function setProjectStatus(id, status) {
  stmts.updateProjectStatus.run(status, id);
}
function deleteProject(id) {
  return stmts.deleteProject.run(id);
}

function insertFile(f) {
  return stmts.insertFile.run(
    f.id, f.projectId, f.discipline, f.filename, f.format,
    f.sizeBytes, f.sha256, f.storedPath,
    f.parseMeta ? JSON.stringify(f.parseMeta) : null,
    f.parseStatus || 'pending'
  );
}
function updateFileParse(id, parseMeta, parseStatus, parseError) {
  stmts.updateFileParse.run(
    parseMeta ? JSON.stringify(parseMeta) : null,
    parseStatus, parseError || null, id
  );
}
function getFilesForProject(id) {
  return stmts.getFilesForProject.all(id);
}

function insertEntities(rows) {
  const tx = db.transaction((batch) => {
    for (const r of batch) {
      stmts.insertEntitiesBatch.run(
        r.id, r.projectId, r.discipline, r.sheet || 'default', r.kind,
        r.label || null, r.x_mm ?? null, r.y_mm ?? null,
        r.w_mm ?? null, r.h_mm ?? null, r.rotation ?? null,
        r.meta ? JSON.stringify(r.meta) : null
      );
    }
  });
  tx(rows);
}
function clearEntitiesForProject(id) {
  db.prepare(`DELETE FROM entities WHERE project_id = ?`).run(id);
}
function getEntitiesForProject(id) {
  // Parse meta JSON back into an object so the canvas renderer can read
  // startPoint / endPoint / vertices etc.
  return stmts.getEntitiesForProject.all(id).map((r) => ({
    ...r,
    meta: r.meta ? safeJson(r.meta) : null,
  }));
}

function safeJson(s) { try { return JSON.parse(s); } catch { return null; } }

function insertIssues(rows) {
  const tx = db.transaction((batch) => {
    for (const r of batch) {
      stmts.insertIssue.run(
        r.id, r.projectId, r.severity, r.category, r.code, r.title,
        r.evidence || null, r.sheet || null, r.grid || null,
        r.mech_ref || null, r.str_ref || null,
        r.formula || null, r.result_json ? JSON.stringify(r.result_json) : null,
        r.state || 'open', r.assigned || null,
        r.created_at || Date.now()
      );
    }
  });
  tx(rows);
}
function clearIssuesForProject(id) {
  stmts.clearIssuesForProject.run(id);
}
function getIssuesForProject(id) {
  return stmts.getIssuesForProject.all(id).map((r) => ({
    ...r,
    result: r.result_json ? JSON.parse(r.result_json) : null,
    meta: null,
  }));
}

function rowToProject(r) {
  return {
    id: r.id,
    label: r.label,
    shortName: r.short_name,
    rev: r.rev,
    kind: r.kind,
    status: r.status,
    createdAt: r.created_at,
    lastOpened: r.last_opened,
  };
}

module.exports = {
  db,
  insertProject, getProject, listProjects, touchProject, setProjectStatus, deleteProject,
  insertFile, updateFileParse, getFilesForProject,
  insertEntities, clearEntitiesForProject, getEntitiesForProject,
  insertIssues, clearIssuesForProject, getIssuesForProject,
};
