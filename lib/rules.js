// lib/rules.js — deterministic L4 cross-checks (subset of BACKEND_ARCHITECTURE §5).
// Runs AFTER Gemini normalisation to cross-reference its outputs with the
// parsed DXF entities table (when DXF parsing succeeded).
'use strict';

/** Run deterministic checks against extracted entities + Gemini output.
 *  Returns extra issues[] that the LLM might have missed. */
function runChecks({ entities, geminiIssues }) {
  const extra = [];
  const now = Date.now();

  // ---- Check 7: required-but-missing openings ----
  // (When DXF parsed cleanly, cross-reference mech openings against str openings.)
  const mechOpenings = entities.filter((e) => e.discipline === 'mech' && (e.kind === 'opening' || e.kind === 'duct' || e.kind === 'pipe'));
  const strOpenings  = entities.filter((e) => e.discipline === 'str'  && (e.kind === 'opening'));

  // Cheap fuzzy match by label/tag
  const matchedStr = new Set();
  for (const m of mechOpenings) {
    if (!m.label) continue;
    let best = null, bestScore = 0;
    for (const s of strOpenings) {
      if (!s.label || matchedStr.has(s.id)) continue;
      const score = simpleSimilarity(m.label, s.label);
      if (score > bestScore && score > 0.55) { bestScore = score; best = s; }
    }
    if (best) matchedStr.add(best.id);
    else if (m.kind === 'opening' || m.kind === 'duct') {
      extra.push({
        severity: 'high',
        category: 'missing',
        code: 'OPEN-MISS',
        title: `Mech opening "${m.label}" has no Str counterpart`,
        evidence: `Required by Mech on layer ${m.meta?.layer || '?'}; no structural opening with a matching tag found in the Str drawing.`,
        sheet: m.sheet || null,
        grid: null,
        mech_ref: m.label,
        str_ref: null,
        formula: `match("${m.label}") → none (threshold 0.55)`,
        created_at: now,
      });
    }
  }
  // Check 8: orphan openings in Str
  for (const s of strOpenings) {
    if (!matchedStr.has(s.id) && s.label) {
      extra.push({
        severity: 'medium',
        category: 'orphan',
        code: 'OPEN-ORPH',
        title: `Str opening "${s.label}" is not required by Mech`,
        evidence: `Opening exists in Str (layer ${s.meta?.layer || '?'}) but no Mech element references it.`,
        sheet: s.sheet || null,
        grid: null,
        mech_ref: null,
        str_ref: s.label,
        formula: `no mech match for "${s.label}"`,
        created_at: now,
      });
    }
  }

  return extra;
}

function simpleSimilarity(a, b) {
  a = String(a).toUpperCase().replace(/[^A-Z0-9]/g, '');
  b = String(b).toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!a || !b) return 0;
  // Jaccard on 3-grams
  const grams = (s) => {
    const out = new Set();
    for (let i = 0; i <= s.length - 3; i++) out.add(s.slice(i, i + 3));
    return out;
  };
  const A = grams(a), B = grams(b);
  let inter = 0;
  for (const g of A) if (B.has(g)) inter++;
  return inter / (A.size + B.size - inter);
}

module.exports = { runChecks, simpleSimilarity };
