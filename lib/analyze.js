// lib/analyze.js — two-phase orchestrator.
//   Phase 1 (sync, fast): parse files → run deterministic rules → persist
//                          + mark project 'ready' so UI updates in <1 s.
//   Phase 2 (async, slow): call Gemini with a hard 20s timeout → persist
//                          any new LLM issues → merge into the existing set.
'use strict';

const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');

const db = require('./db');
const { parseFile, dxfToEntities } = require('./parse');
const { analyseDrawings, geminiConfigured } = require('./gemini');
const { runChecks } = require('./rules');

const analysisState = new Map(); // projectId → { phase, status, startedAt, finishedAt, error, summary, llmStatus }

function getAnalysisState(projectId) {
  return analysisState.get(projectId) || { status: 'idle', summary: null, error: null };
}

const GEMINI_TIMEOUT_MS = 20_000;

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms);
    promise.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); }
    );
  });
}

/** Compute + persist summary from a list of issues. */
function summarize(allIssues) {
  const summary = { pass: 0, warn: 0, fail: 0 };
  for (const it of allIssues) {
    if (it.severity === 'high') summary.fail++;
    else if (it.severity === 'medium' || it.severity === 'low') summary.warn++;
    else if (it.severity === 'pass') summary.pass++;
  }
  return summary;
}

/** Phase 1 — synchronous-ish: parse + rule check + persist + mark ready.
 *  Returns within ~1 second; doesn't call Gemini. */
async function runPhase1(projectId) {
  analysisState.set(projectId, {
    status: 'running', phase: 'rules', startedAt: Date.now(), error: null,
  });
  db.setProjectStatus(projectId, 'processing');

  const project = db.getProject(projectId);
  if (!project) throw new Error('Project not found');
  const files = db.getFilesForProject(projectId);
  const str  = files.find((f) => f.discipline === 'str');
  const mech = files.find((f) => f.discipline === 'mech');
  if (!str || !mech) throw new Error('Project is missing STR or MECH file');

  const DATA_DIR = process.env.DATA_DIR || './data';
  const strParsed  = await ensureParsed(str,  DATA_DIR);
  const mechParsed = await ensureParsed(mech, DATA_DIR);

  // Persist extracted entities (only when DXF parsed cleanly)
  const allEntities = [
    ...dxfToEntities(strParsed,  'str',  projectId, uuidv4),
    ...dxfToEntities(mechParsed, 'mech', projectId, uuidv4),
  ];
  if (allEntities.length) {
    db.clearEntitiesForProject(projectId);
    db.insertEntities(allEntities);
  }

  // Deterministic rules — runs against the parsed entities
  const ruleIssues = runChecks({
    entities: db.getEntitiesForProject(projectId),
    geminiIssues: [],
  }).map((it) => ({ id: uuidv4(), projectId, ...it, state: 'open', assigned: null, created_at: Date.now() }));

  db.clearIssuesForProject(projectId);
  if (ruleIssues.length) db.insertIssues(ruleIssues);

  const summary = summarize(ruleIssues);
  db.setProjectStatus(projectId, 'ready');
  analysisState.set(projectId, {
    status: 'done', phase: 'rules', finishedAt: Date.now(),
    summary, issueCount: ruleIssues.length,
    llmStatus: geminiConfigured() ? 'pending' : 'skipped',
    error: null,
  });
  return { ruleIssues, summary };
}

/** Phase 2 — slow: Gemini call with hard timeout. Adds LLM issues to the DB. */
async function runPhase2(projectId) {
  const project = db.getProject(projectId);
  if (!project) return;
  const files = db.getFilesForProject(projectId);
  const str  = files.find((f) => f.discipline === 'str');
  const mech = files.find((f) => f.discipline === 'mech');
  if (!str || !mech || !geminiConfigured()) {
    analysisState.set(projectId, { ...(analysisState.get(projectId) || {}), llmStatus: 'skipped' });
    return;
  }

  analysisState.set(projectId, { ...(analysisState.get(projectId) || {}), llmStatus: 'running' });

  let geminiIssues = [];
  let geminiError = null;
  try {
    geminiIssues = await withTimeout(
      analyseDrawings({
        projectMeta: { label: project.label, rev: project.rev, createdAt: project.createdAt },
        strMeta:  { ...str.parseMeta,  filename: str.filename,  format: str.format,  sizeBytes: str.size_bytes, parseStatus: str.parse_status, kind: str.parse_meta?.kind || 'unknown', header: str.parse_meta?.header || null },
        mechMeta: { ...mech.parseMeta, filename: mech.filename, format: mech.format, sizeBytes: mech.size_bytes, parseStatus: mech.parse_status, kind: mech.parse_meta?.kind || 'unknown', header: mech.parse_meta?.header || null },
      }),
      GEMINI_TIMEOUT_MS,
      'Gemini'
    );
  } catch (e) {
    geminiError = e.message || String(e);
    console.error(`[gemini] ${projectId}: ${geminiError}`);
    geminiIssues = [{
      severity: 'low',
      category: 'general',
      code: geminiError.includes('timed out') ? 'AI-TIMEOUT' : 'AI-UNAVAIL',
      title: geminiError.includes('timed out') ? 'Gemini analysis timed out' : 'Gemini analysis unavailable',
      evidence: `${geminiError.slice(0, 200)}. Deterministic rule engine results are still shown above.`,
      formula: null, sheet: null, grid: null, mech_ref: null, str_ref: null,
    }];
  }

  // Append LLM issues to the existing rule-engine issues
  const newIssues = geminiIssues.map((it) => ({
    id: uuidv4(), projectId, ...it, state: 'open', assigned: null, created_at: Date.now(),
  }));
  if (newIssues.length) db.insertIssues(newIssues);

  // Recompute summary
  const allIssues = db.getIssuesForProject(projectId);
  const summary = summarize(allIssues);
  analysisState.set(projectId, {
    ...(analysisState.get(projectId) || {}),
    llmStatus: geminiError ? 'failed' : 'done',
    llmError: geminiError,
    finishedAt: Date.now(),
    summary,
    issueCount: allIssues.length,
  });
}

/** Run the full two-phase pipeline.
 *  Phase 1 runs synchronously (await), then returns; phase 2 runs async. */
async function runAnalysis(projectId) {
  try {
    await runPhase1(projectId);
  } catch (err) {
    db.setProjectStatus(projectId, 'error');
    analysisState.set(projectId, { status: 'error', error: err.message || String(err) });
    throw err;
  }
  // Phase 2 in the background — don't await; the HTTP request already returned
  setImmediate(() => {
    runPhase2(projectId).catch((err) => {
      console.error(`[phase2] ${projectId}:`, err.message || err);
    });
  });
  return { status: 'done', phase: 'rules' };
}

async function ensureParsed(fileRow, dataDir) {
  const fullPath = path.join(dataDir, fileRow.stored_path);
  // Always re-parse the file: the parse_meta cache only stores file-level
  // metadata, not the entity list. dxfToEntities() needs the full parsed
  // object with .entities[] — and we also want to pick up any improvements
  // to the parser without manually invalidating the cache.
  const result = await parseFile(fullPath, fileRow.filename);
  // Only persist the file-level metadata if it changed
  const prevMeta = fileRow.parse_meta ? JSON.parse(fileRow.parse_meta) : {};
  if (
    prevMeta.entityCount !== result.entityCount ||
    prevMeta.headerUnits !== result.header?.$INSUNITS
  ) {
    const meta = {
      kind: result.kind,
      parseStatus: result.parseStatus || (result.ok ? 'ok' : 'failed'),
      error: result.error || null,
      entityCount: result.entityCount,
      layers: result.layers,
      textLabels: result.textLabels,
      headerUnits: result.header?.$INSUNITS,
      header: result.header,
      parseMeta: result.parseMeta,
      magicBytes: result.parseMeta?.magicBytes,
      dwgVersion: result.parseMeta?.dwgVersion,
      layerCandidates: result.parseMeta?.layerCandidates,
      elevations: result.parseMeta?.elevations,
      pipes: result.parseMeta?.pipes,
      ifcClasses: result.parseMeta?.ifcClasses,
    };
    db.updateFileParse(fileRow.id, meta, meta.parseStatus, meta.error);
  }
  return result;
}

module.exports = { runAnalysis, getAnalysisState };
