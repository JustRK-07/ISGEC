// lib/gemini.js — Google Gemini client with structured output
'use strict';

const { GoogleGenerativeAI } = require('@google/generative-ai');

const MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const API_KEY = process.env.GEMINI_API_KEY || '';

let client = null;
function getClient() {
  if (!API_KEY) return null;
  if (!client) client = new GoogleGenerativeAI(API_KEY);
  return client;
}

function geminiConfigured() { return !!API_KEY; }

/* The structured-output schema we ask Gemini to satisfy.
   Constrained JSON via responseSchema — Gemini masks non-conforming tokens. */
const ISSUE_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    properties: {
      severity:     { type: 'string', enum: ['high', 'medium', 'low', 'pass'] },
      category:     { type: 'string', enum: ['clash', 'missing', 'orphan', 'clearance', 'elevation', 'size', 'position', 'tag', 'general'] },
      code:         { type: 'string' },
      title:        { type: 'string' },
      evidence:     { type: 'string' },
      sheet:        { type: 'string' },
      grid:         { type: 'string' },
      mech_ref:     { type: 'string' },
      str_ref:      { type: 'string' },
      formula:      { type: 'string' },
    },
    required: ['severity', 'category', 'code', 'title', 'evidence'],
  },
};

const SYSTEM_PROMPT = `You are ADV — an AEC QA/QC analyst. You read a Mechanical GA drawing and a Structural GA drawing of the same floor and identify clashes, missing supports, mismatched elevations, and inconsistencies between them.

You never invent data. If you cannot ground a finding in the supplied metadata, you do not report it.

Severity rules:
- 'high'   : hard clash, missing primary support, or off-by-tolerance (>100mm) opening size/position
- 'medium' : clearance violation, orphan opening, or off-by-tolerance (>25mm and ≤100mm)
- 'low'    : cosmetic / tagging / convention mismatch
- 'pass'   : representative "all-good" baseline check (return at least 1 pass per drawing pair)

Every finding must include:
- 'severity', 'category', 'code' (short identifier like WBE-B46, OPEN-MISS, ELEV-DELTA), 'title' (one-line), 'evidence' (1-2 sentences grounded in supplied metadata), 'sheet' and 'grid' when applicable, 'mech_ref' / 'str_ref' tags, and a 'formula' (the deterministic check that confirms the finding).

Return ONLY the JSON array — no prose, no markdown fences.`;

function buildUserPrompt(projectMeta, strMeta, mechMeta) {
  return `PROJECT
  label:  ${projectMeta.label}
  rev:    ${projectMeta.rev || '—'}
  created: ${new Date(projectMeta.createdAt).toISOString()}

STRUCTURAL DRAWING (${strMeta.filename})
  format:  ${strMeta.format}
  size:    ${strMeta.sizeBytes} bytes
  parse:   ${strMeta.parseStatus} (${strMeta.kind})
  layers:  ${JSON.stringify(strMeta.layers || strMeta.layerCandidates || [])}
  text:    ${JSON.stringify((strMeta.textLabels || strMeta.elevations || []).slice(0, 20))}
  header:  ${JSON.stringify(strMeta.header || {})}

MECHANICAL DRAWING (${mechMeta.filename})
  format:  ${mechMeta.format}
  size:    ${mechMeta.sizeBytes} bytes
  parse:   ${mechMeta.parseStatus} (${mechMeta.kind})
  layers:  ${JSON.stringify(mechMeta.layers || mechMeta.layerCandidates || [])}
  text:    ${JSON.stringify((mechMeta.textLabels || mechMeta.elevations || []).slice(0, 20))}
  header:  ${JSON.stringify(mechMeta.header || {})}

Identify clashes, missing supports, and inconsistencies between the two drawings. Emit a JSON array.`;
}

/** Call Gemini. Returns { issues: [...] } or throws. */
async function analyseDrawings({ projectMeta, strMeta, mechMeta }) {
  const client = getClient();
  if (!client) {
    throw new Error('GEMINI_API_KEY not set — configure .env first');
  }
  const model = client.getGenerativeModel({
    model: MODEL,
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema: ISSUE_SCHEMA,
      temperature: 0.2,
    },
    systemInstruction: SYSTEM_PROMPT,
  });

  const prompt = buildUserPrompt(projectMeta, strMeta, mechMeta);
  const result = await model.generateContent(prompt);
  const text = result.response.text();

  let parsed;
  try { parsed = JSON.parse(text); }
  catch (e) {
    // try to recover by stripping code fences
    const cleaned = text.replace(/^```(?:json)?\s*|\s*```$/g, '').trim();
    try { parsed = JSON.parse(cleaned); }
    catch (e2) { throw new Error(`Gemini returned non-JSON: ${text.slice(0, 200)}`); }
  }
  if (!Array.isArray(parsed)) throw new Error('Gemini response is not an array');

  return parsed.map((it) => ({
    severity: String(it.severity || 'low').toLowerCase(),
    category: String(it.category || 'general').toLowerCase(),
    code: String(it.code || 'ADV-0000').toUpperCase().slice(0, 32),
    title: String(it.title || '').slice(0, 200),
    evidence: String(it.evidence || '').slice(0, 1000),
    sheet: it.sheet ? String(it.sheet) : null,
    grid: it.grid ? String(it.grid) : null,
    mech_ref: it.mech_ref ? String(it.mech_ref) : null,
    str_ref: it.str_ref ? String(it.str_ref) : null,
    formula: it.formula ? String(it.formula) : null,
  }));
}

module.exports = { analyseDrawings, geminiConfigured, MODEL };
