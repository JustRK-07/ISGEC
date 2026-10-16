// server.js — ADV backend bootstrap
'use strict';

require('dotenv').config();

const path = require('path');
const fs = require('fs');
const express = require('express');
const cors = require('cors');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');

const db = require('./lib/db');
const { upload, MulterError, persistUpload, UPLOADS_DIR, MAX_FILE_SIZE } = require('./lib/upload');
const { runAnalysis, getAnalysisState } = require('./lib/analyze');
const { geminiConfigured, MODEL } = require('./lib/gemini');

const PORT = parseInt(process.env.PORT || '3001', 10);
const PROJECT_ROOT = __dirname;
const INDEX_HTML = path.join(PROJECT_ROOT, 'index.html');

const app = express();
app.use(cors());
app.use(express.json({ limit: '2mb' }));

/* ============================================================
   API ROUTES
   ============================================================ */

// Health check — also confirms Gemini key is loaded
app.get('/api/health', (req, res) => {
  res.json({
    ok: true,
    gemini: geminiConfigured(),
    model: MODEL,
    uptimeSec: Math.round(process.uptime()),
    dbFile: path.relative(PROJECT_ROOT, db.db.name),
    projectCount: db.listProjects().length,
  });
});

// List projects
app.get('/api/projects', (req, res) => {
  const projects = db.listProjects().map((p) => {
    const issues = db.getIssuesForProject(p.id);
    const summary = { pass: 0, warn: 0, fail: 0 };
    for (const it of issues) {
      if (it.severity === 'high') summary.fail++;
      else if (it.severity === 'medium' || it.severity === 'low') summary.warn++;
      else if (it.severity === 'pass') summary.pass++;
    }
    return { ...p, summary };
  });
  res.json(projects);
});

// Create a project — multipart upload of STR + MECH (+ optional extra)
app.post('/api/projects', upload.fields([
  { name: 'str',   maxCount: 1 },
  { name: 'mech',  maxCount: 1 },
  { name: 'extra', maxCount: 1 },
]), async (req, res, next) => {
  try {
    if (!req.files || !req.files.str || !req.files.mech) {
      return res.status(400).json({
        error: 'Both STR and MECH files are required.',
        code: 'MISSING_FILES',
      });
    }
    const label = (req.body.label || '').trim() || `Untitled · ${new Date().toISOString().slice(0, 16)}`;
    const rev = (req.body.rev || '').trim() || null;

    const projectId = uuidv4();
    const now = Date.now();

    db.insertProject({
      id: projectId,
      label,
      shortName: label,
      rev,
      kind: 'Str + Mech',
      status: 'processing',
      createdAt: now,
      lastOpened: now,
    });

    const filesMeta = { str: null, mech: null, extra: null };
    for (const disc of ['str', 'mech', 'extra']) {
      const file = req.files[disc] && req.files[disc][0];
      if (!file) continue;
      const stored = persistUpload(file.buffer, projectId, disc, file.originalname);
      const fileId = uuidv4();
      db.insertFile({
        id: fileId,
        projectId,
        discipline: disc,
        filename: file.originalname,
        format: stored.format,
        sizeBytes: stored.sizeBytes,
        sha256: stored.sha256,
        storedPath: stored.storedPath,
        parseMeta: null,
        parseStatus: 'pending',
      });
      filesMeta[disc] = { id: fileId, filename: file.originalname, format: stored.format, sizeBytes: stored.sizeBytes, sha256: stored.sha256 };
    }

    // Kick off analysis in the background; client polls /api/projects/:id/analysis
    setImmediate(() => {
      runAnalysis(projectId).catch((err) => {
        console.error(`[analyze] ${projectId}:`, err.message || err);
      });
    });

    res.status(201).json({
      id: projectId,
      label,
      shortName: label,
      rev,
      status: 'processing',
      createdAt: now,
      lastOpened: now,
      files: filesMeta,
    });
  } catch (err) { next(err); }
});

// Get full project detail
app.get('/api/projects/:id', (req, res) => {
  const project = db.getProject(req.params.id);
  if (!project) return res.status(404).json({ error: 'Project not found', code: 'NOT_FOUND' });
  db.touchProject(project.id);
  const files = db.getFilesForProject(project.id);
  const issues = db.getIssuesForProject(project.id);
  const entities = db.getEntitiesForProject(project.id);
  const analysis = getAnalysisState(project.id);

  // Bucket entities by discipline for the workspace
  const entityBuckets = { str: [], mech: [] };
  for (const e of entities) {
    if (entityBuckets[e.discipline]) entityBuckets[e.discipline].push(e);
  }

  // Sheets discovered from entities + a default '0001'
  const sheets = new Set(['0001']);
  for (const e of entities) if (e.sheet) sheets.add(e.sheet);

  const summary = { pass: 0, warn: 0, fail: 0 };
  for (const it of issues) {
    if (it.severity === 'high') summary.fail++;
    else if (it.severity === 'medium' || it.severity === 'low') summary.warn++;
    else if (it.severity === 'pass') summary.pass++;
  }

  res.json({
    ...project,
    files: files.map((f) => ({
      id: f.id, discipline: f.discipline, filename: f.filename, format: f.format,
      sizeBytes: f.size_bytes, sha256: f.sha256, parseStatus: f.parse_status, parseMeta: f.parse_meta,
    })),
    issues,
    entities: entityBuckets,
    sheets: [...sheets].sort(),
    analysis,
    summary,
  });
});

// Trigger (or re-trigger) analysis
app.post('/api/projects/:id/analyze', async (req, res, next) => {
  try {
    const project = db.getProject(req.params.id);
    if (!project) return res.status(404).json({ error: 'Project not found', code: 'NOT_FOUND' });
    if (!geminiConfigured()) {
      return res.status(503).json({
        error: 'GEMINI_API_KEY not set. Add it to .env and restart.',
        code: 'NO_GEMINI_KEY',
      });
    }
    // Run async; respond immediately with 'running'
    setImmediate(() => {
      runAnalysis(project.id).catch((err) => {
        console.error(`[analyze] ${project.id}:`, err.message || err);
      });
    });
    res.json({ status: 'running' });
  } catch (err) { next(err); }
});

// Poll analysis status
app.get('/api/projects/:id/analysis', (req, res) => {
  const project = db.getProject(req.params.id);
  if (!project) return res.status(404).json({ error: 'Project not found', code: 'NOT_FOUND' });
  const state = getAnalysisState(project.id);
  res.json({
    status: state.status,
    phase: state.phase || null,
    llmStatus: state.llmStatus || null,
    llmError: state.llmError || null,
    summary: state.summary || null,
    issueCount: state.issueCount || null,
    error: state.error || null,
    startedAt: state.startedAt || null,
    finishedAt: state.finishedAt || null,
  });
});

// Update issue state (resolve / dismiss / re-open / assign)
app.patch('/api/issues/:id', (req, res) => {
  const { state, assigned } = req.body || {};
  const allowed = ['open', 'resolved', 'dismissed'];
  if (state && !allowed.includes(state)) {
    return res.status(400).json({ error: `state must be one of ${allowed.join(', ')}`, code: 'BAD_STATE' });
  }
  const issue = db.db.prepare(`SELECT * FROM issues WHERE id = ?`).get(req.params.id);
  if (!issue) return res.status(404).json({ error: 'Issue not found', code: 'NOT_FOUND' });
  const newState = state || issue.state;
  const newAssigned = assigned !== undefined ? assigned : issue.assigned;
  db.db.prepare(`UPDATE issues SET state = ?, assigned = ? WHERE id = ?`).run(newState, newAssigned, req.params.id);
  res.json({ ok: true, id: req.params.id, state: newState, assigned: newAssigned });
});

// Delete project
app.delete('/api/projects/:id', (req, res) => {
  const project = db.getProject(req.params.id);
  if (!project) return res.status(404).json({ error: 'Project not found', code: 'NOT_FOUND' });
  // Remove uploaded files from disk
  const projectDir = path.join(UPLOADS_DIR, project.id);
  if (fs.existsSync(projectDir)) fs.rmSync(projectDir, { recursive: true, force: true });
  db.deleteProject(project.id);
  res.json({ ok: true });
});

// Serve uploaded files (raw bytes) for any future "view drawing" links
app.get('/uploads/:projectId/:filename', (req, res) => {
  const projectDir = path.join(UPLOADS_DIR, req.params.projectId);
  const fullPath = path.join(projectDir, req.params.filename);
  if (!fs.existsSync(fullPath)) return res.status(404).json({ error: 'Not found', code: 'NOT_FOUND' });
  res.sendFile(fullPath);
});

/* ============================================================
   STATIC FILES (serve index.html + everything else from repo root)
   ============================================================ */
app.use(express.static(PROJECT_ROOT, { extensions: ['html'] }));

/* ============================================================
   ERROR HANDLER
   ============================================================ */
app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    const status = err.code === 'LIMIT_FILE_SIZE' ? 413 : 400;
    return res.status(status).json({ error: err.message, code: err.code });
  }
  if (err instanceof MulterError) {
    return res.status(err.httpStatus || 400).json({ error: err.message, code: 'BAD_FILE' });
  }
  console.error('[unhandled]', err);
  res.status(500).json({ error: err.message || 'Internal error', code: 'INTERNAL' });
});

app.listen(PORT, () => {
  console.log(`\n  ADV backend listening on http://localhost:${PORT}`);
  console.log(`  Gemini configured: ${geminiConfigured()} (model: ${MODEL})`);
  console.log(`  DB file: ${path.relative(PROJECT_ROOT, db.db.name)}`);
  console.log(`  Upload cap: ${(MAX_FILE_SIZE / 1024 / 1024).toFixed(0)} MB\n`);
});
