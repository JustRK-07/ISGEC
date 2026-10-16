// lib/parse.js — DXF entity extraction + DWG metadata extraction
'use strict';

const fs = require('fs');
const path = require('path');

// DWG version tags — every real DWG starts with one of these
// (Ref: Open Design Alliance "DWG File Format Spec")
const DWG_VERSIONS = {
  AC1012: 'R13',   AC1013: 'R13c',  AC1014: 'R14',   AC1015: 'R2000',
  AC1018: 'R2004', AC1021: 'R2007', AC1024: 'R2010', AC1027: 'R2013',
  AC1032: 'R2018',
};

// AutoCAD $INSUNITS → multiplier to convert to millimetres.
//   0 = unitless, 1 = inches, 2 = feet, 4 = mm, 5 = cm, 6 = metres
//   (codes 3, 7, 8, 9 are non-length units we don't expect on GA drawings)
const INSUNITS_TO_MM = {
  0: 1, 1: 25.4, 2: 304.8, 4: 1, 5: 10, 6: 1000,
};
function unitsToMm(insUnits) {
  return INSUNITS_TO_MM[insUnits] || 1;
}

/** Detect file type + extract metadata.
 *  Returns { ok, kind, layers[], textLabels[], entityCount, header, parseMeta, error }
 */
async function parseFile(filePath, originalName) {
  const ext = path.extname(originalName || filePath).toLowerCase();
  const buf = fs.readFileSync(filePath);
  if (ext === '.dxf') return parseDxf(buf, originalName);
  if (ext === '.dwg') return parseDwg(buf, originalName, filePath);
  if (ext === '.ifc') return parseIfc(buf, originalName);
  if (ext === '.pdf') return parsePdfStub(originalName);
  return { ok: false, kind: 'unknown', error: `Unsupported extension ${ext}` };
}

/** Convert a real DWG file to DXF using the local libredwg binary, then
 *  hand the resulting DXF bytes to parseDxf() for full entity extraction.
 *  Returns the same shape as parseDxf(). */
function convertDwgToDxf(dwgPath) {
  const { spawnSync } = require('child_process');
  // Look for dwg2dxf on PATH or in $HOME/local/bin
  const candidates = [
    process.env.DWG2DXF_PATH,
    `${process.env.HOME}/local/bin/dwg2dxf`,
    '/usr/local/bin/dwg2dxf',
    '/usr/bin/dwg2dxf',
  ].filter(Boolean);
  let bin = null;
  for (const p of candidates) {
    if (fs.existsSync(p)) { bin = p; break; }
  }
  if (!bin) {
    const pathHit = spawnSync('which', ['dwg2dxf']).stdout?.toString().trim();
    if (pathHit) bin = pathHit;
  }
  if (!bin) {
    return { ok: false, error: 'dwg2dxf not found — install libredwg (e.g. `~/local/bin/dwg2dxf`)' };
  }
  const tmpDir = require('os').tmpdir();
  const out = require('path').join(tmpDir, `dwg2dxf-${Date.now()}-${Math.random().toString(36).slice(2,8)}.dxf`);
  const r = spawnSync(bin, ['-y', '-o', out, dwgPath], { timeout: 120_000, encoding: 'utf8' });
  if (r.status !== 0 || !fs.existsSync(out)) {
    const msg = (r.stderr || r.stdout || 'dwg2dxf failed').toString().split('\n').slice(-5).join(' ');
    return { ok: false, error: `dwg2dxf failed: ${msg.slice(0, 300)}` };
  }
  const buf = fs.readFileSync(out);
  try { fs.unlinkSync(out); } catch (_) {}
  return { ok: true, dxfBuf: buf, dwg2dxfPath: bin };
}

/* ============================================================
   DXF — custom tolerant parser (Node-side, fast, libredwg-friendly)
   Recovers from broken DXF (unescaped newlines in MTEXT, etc.)
   ============================================================ */

// Valid DXF group codes are 0..1071. Anything else = corrupted sync.
const VALID_GROUP_MAX = 1071;

/** Custom DXF parser — handles libredwg-generated files that have
 *  unusual group codes (5, 100, 330, etc.) and broken text values
 *  (unescaped newlines inside MTEXT) without throwing. */
function parseDxf(buf, name) {
  const text = buf.toString('utf8');
  const lines = text.split(/\r?\n/);

  // ---- Parse code/value pairs, RECOVERING from desync ----
  // We walk the file in (line, value-line) pairs, but if the "code" line
  // doesn't parse as an integer 0..1071, we treat it as a continuation
  // of the previous value (i.e. the previous text got split across lines
  // because libredwg didn't escape an embedded newline).
  const tokens = [];
  let i = 0;
  while (i < lines.length - 1) {
    const rawCode = lines[i];
    const rawValue = lines[i + 1] ?? '';
    const code = parseInt(rawCode, 10);
    if (isNaN(code) || code < 0 || code > VALID_GROUP_MAX) {
      // Desync — treat rawCode as a continuation of the previous value
      if (tokens.length > 0) {
        const last = tokens[tokens.length - 1];
        last[1] = last[1] + '\n' + rawCode;
      }
      i += 1; // skip just this line, the next line is still a value
      continue;
    }
    tokens.push([code, rawValue]);
    i += 2;
  }

  // ---- Pass 0: scan the HEADER section for $INSUNITS ----
  // (DXF puts header vars in their own section; the entity loop below only
  //  walks ENTITIES/BLOCKS so we'd otherwise miss it.)
  let insUnits = null;
  let inHeader = false;
  for (let k = 0; k < tokens.length; k++) {
    const [c, v] = tokens[k];
    // DXF section header: 0 SECTION → 2 <NAME> → ... → 0 ENDSEC
    if (c === 0 && v === 'SECTION' && k + 1 < tokens.length && tokens[k + 1][0] === 2) {
      inHeader = (tokens[k + 1][1] === 'HEADER');
      k++;  // skip the name token
      continue;
    }
    if (c === 0 && (v === 'ENDSEC' || v === 'EOF')) inHeader = false;
    if (inHeader && c === 9 && v === '$INSUNITS') {
      if (k + 1 < tokens.length && tokens[k + 1][0] === 70) {
        insUnits = parseInt(tokens[k + 1][1], 10);
      }
    }
  }

  // ---- Find ENTITIES section bounds (libredwg puts entities inside
  // BLOCKS section as part of *Model_Space / *Paper_Space blocks; we
  // accept either section and only count entities that are NOT inside a
  // user-defined BLOCK definition). ----
  const entities = [];
  let inEntities = false;
  let lastEntityStart = -1;
  let blockDepth = 0;     // inside a USER-DEFINED block (skip its entities)
  let inModelBlock = false;  // inside *Model_Space / *Paper_Space (KEEP entities)
  i = 0;
  while (i < tokens.length) {
    const [code, value] = tokens[i];
    if (code === 2 && (value === 'ENTITIES' || value === 'BLOCKS')) {
      inEntities = true; i++; continue;
    }
    if (inEntities && code === 0 && (value === 'ENDSEC' || value === 'EOF')) {
      inEntities = false; break;
    }
    // Look at BLOCK opens to decide whether to keep or skip its entities
    if (inEntities && code === 0 && value === 'BLOCK') {
      // Peek ahead for the block name (code 2 typically follows)
      let blockName = '';
      for (let j = i + 1; j < Math.min(i + 8, tokens.length); j++) {
        if (tokens[j][0] === 0) break;
        if (tokens[j][0] === 2) { blockName = tokens[j][1]; break; }
      }
      if (blockName.startsWith('*Model_Space') || blockName.startsWith('*Paper_Space') || blockName.startsWith('*')) {
        // Any space-prefixed block is the special "layout" block — keep its entities
        inModelBlock = true;
      } else {
        blockDepth++;
      }
      i++; continue;
    }
    if (inEntities && code === 0 && value === 'ENDBLK') {
      if (blockDepth > 0) blockDepth--;
      else if (inModelBlock) inModelBlock = false;
      i++; continue;
    }
    // Count ALL code=0 entities regardless of which block we're inside.
    // (User-defined blocks often contain real model entities — especially
    //  in assembly drawings where *Model_Space is empty.)
    if (inEntities && code === 0) {
      if (i > lastEntityStart) {
        const ent = parseDxfEntity(tokens, i);
        if (ent) { entities.push(ent.rec); lastEntityStart = i; i = ent.next; continue; }
      }
      lastEntityStart = i;
    }
    i++;
  }

  // ---- Build summary ----
  const layerMap = new Map();
  const labels = [];
  for (const e of entities) {
    const layerName = e.layer || '0';
    layerMap.set(layerName, (layerMap.get(layerName) || 0) + 1);
    if ((e.type === 'TEXT' || e.type === 'MTEXT') && e.text) {
      labels.push({ layer: layerName, text: String(e.text).slice(0, 200) });
    }
  }
  const layers = [...layerMap.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 60)
    .map(([name, count]) => ({ name, count }));

  return {
    ok: true,
    kind: 'dxf',
    entities,
    entityCount: entities.length,
    layers,
    textLabels: labels.slice(0, 200),
    header: { $INSUNITS: insUnits },
    parseMeta: {
      kind: 'dxf',
      parser: 'custom',
      entityCount: entities.length,
      layers,
      headerUnits: insUnits,
      textLabels: labels.slice(0, 200),
    },
  };
}

/** Parse a single entity starting at index i (where tokens[i] is the
 *  code-0 entity-type line). Returns { rec, next } or null on failure. */
function parseDxfEntity(tokens, i) {
  const type = (tokens[i][1] || '').toUpperCase();
  // Skip none / unused
  if (!type || type === 'ENDBLK' || type === 'ENDSEC' || type === 'EOF') return null;

  const rec = { type };
  let j = i + 1;
  // Scan until next code-0 (next entity) or ENDSEC/EOF
  let textBuf = [];
  // LWPOLYLINE / POLYLINE: capture all (10,20) pairs as vertices, not just the first
  const isPoly = (type === 'LWPOLYLINE' || type === 'POLYLINE');
  if (isPoly) rec.vertices = [];
  while (j < tokens.length) {
    const [code, value] = tokens[j];
    if (code === 0) break;  // next entity
    if (code === 8)  rec.layer = value;
    else if (code === 10) {
      const x = parseFloat(value);
      if (isPoly && rec.vertices.length > 0 && !rec._lastVert) {
        // (10,20) pairs are subsequent vertices on LWPOLYLINE / VERTEX entities
        rec.vertices.push({ x, y: 0 });
        rec._lastVert = true;
      } else {
        rec.x = x; rec._pos10 = (rec._pos10 || { x:0, y:0, z:0 }); rec._pos10.x = rec.x;
        if (isPoly && rec.vertices.length === 0) rec.vertices.push({ x, y: 0 });
        rec._lastVert = false;
      }
    }
    else if (code === 20) {
      const y = parseFloat(value);
      if (isPoly && rec.vertices.length) rec.vertices[rec.vertices.length - 1].y = y;
      if (rec._pos10) rec._pos10.y = y;
    }
    else if (code === 30) { if (rec._pos10) rec._pos10.z = parseFloat(value); }
    // LINE: code 10/20 is the START point; code 11/21 is the END point.
    // TEXT/INSERT/etc: code 10/20 is the position (already captured above as _pos10).
    else if (code === 11) { rec._end = rec._end || { x:0, y:0 }; rec._end.x = parseFloat(value); }
    else if (code === 21) { rec._end = rec._end || { x:0, y:0 }; rec._end.y = parseFloat(value); }
    else if (code === 12) { /* secondary start — ignore for now */ }
    else if (code === 22) { /* secondary end — ignore for now */ }
    else if (code === 40) {
      // For CIRCLE/ARC: 40 = radius. For TEXT: 40 = text height.
      if (type === 'CIRCLE' || type === 'ARC') rec.radius = parseFloat(value);
      else rec.textHeight = parseFloat(value);
    }
    else if (code === 1) textBuf.push(value);
    else if (code === 3) textBuf.push(value);
    else if (code === 50) rec.rotation = parseFloat(value);
    else if (code === 41) rec.scale = parseFloat(value);
    else if (code === 70) rec.flags = parseInt(value, 10);
    else if (code === 72) rec.textHAlign = parseInt(value, 10);
    else if (code === 73) rec.textVAlign = parseInt(value, 10);
    else if (code === 100) { /* subclass marker — skip */ }
    else if (code === 1000 || code === 1001) textBuf.push(value);
    else if (code === 1011 || code === 1020 || code === 1041) { /* xdata scalar */ }
    else if (code === 90) rec.vertexCount = parseInt(value, 10);
    else if (code === 70 && type === 'POLYLINE') rec.polylineFlag = parseInt(value, 10);
    else if (code === 2 && (type === 'INSERT' || type === 'BLOCK')) rec.blockName = value;
    else if (code === 41 && type === 'INSERT') rec.scaleX = parseFloat(value);
    else if (code === 42 && type === 'INSERT') rec.scaleY = parseFloat(value);
    j++;
  }

  if (type === 'TEXT' || type === 'MTEXT') {
    rec.text = textBuf.join('\n').trim();
  }

  if (rec._pos10) {
    rec.position = { x: rec._pos10.x, y: rec._pos10.y };
    // For LINE entities, code 10/20 is the START point (not just position).
    if (type === 'LINE') {
      rec.startPoint = { x: rec._pos10.x, y: rec._pos10.y };
    }
    delete rec._pos10;
  }
  if (rec._end) {
    rec.endPoint = { x: rec._end.x, y: rec._end.y };
    delete rec._end;
  }
  return { rec, next: j };
}

/** Walk the parsed DXF entities into our normalized entities[] table.
 *  Includes TEXT labels as their own rows AND attaches the nearest text label
 *  to each opening/duct/pipe/beam/equipment so the rule engine can match by tag.
 *  Converts all coordinates from the file's drawing units to millimetres using
 *  the $INSUNITS header. */
function dxfToEntities(parsed, discipline, projectId, uuid) {
  if (!parsed.ok || !parsed.entities) return [];
  const u2mm = unitsToMm(parsed.header?.$INSUNITS || 4);  // default to mm if header missing
  const conv = (n) => (n == null ? null : n * u2mm);
  const convPt = (p) => (p ? { x: p.x * u2mm, y: p.y * u2mm } : null);

  const out = [];
  // Pass 1: text labels
  const labels = [];
  for (const e of parsed.entities) {
    const kind = classifyDxfEntity(e);
    const xy = entityCentroid(e);
    if (!xy) continue;
    // Convert ALL geometry to mm so downstream code is consistent
    const xyMm = { x: xy.x * u2mm, y: xy.y * u2mm };
    const dims = entityDims(e);  // dims are in raw units
    const w_mm = dims.w == null ? null : dims.w * u2mm;
    const h_mm = dims.h == null ? null : dims.h * u2mm;
    const isText = (e.type === 'TEXT' || e.type === 'MTEXT');
    const rec = {
      id: uuid(),
      projectId,
      discipline,
      sheet: detectSheet(e.layer || ''),
      kind,
      label: e.text || null,
      x_mm: xyMm.x, y_mm: xyMm.y,
      w_mm, h_mm,
      rotation: e.rotation || 0,
      meta: {
        layer: e.layer || '0',
        type: e.type,
        // Geometry in mm so the canvas renderer can draw actual LINE segments
        // (not dots) and polyline outlines.
        startPoint: convPt(e.startPoint),
        endPoint: convPt(e.endPoint),
        position: convPt(e.position),
        center: convPt(e.center),
        vertices: Array.isArray(e.vertices) ? e.vertices.map(convPt) : null,
        radius: e.radius == null ? null : e.radius * u2mm,
        insUnits: parsed.header?.$INSUNITS || null,
      },
    };
    out.push(rec);
    if (isText && e.text) labels.push({ x: xyMm.x, y: xyMm.y, text: String(e.text), sheet: rec.sheet });
  }
  // Pass 2: attach nearest label to opening/duct/pipe/beam/equipment (radius 800mm in mm space)
  for (const rec of out) {
    if (!['opening', 'duct', 'pipe', 'beam', 'column', 'equipment', 'block'].includes(rec.kind)) continue;
    let best = null, bestDist = Infinity;
    for (const l of labels) {
      if (l.sheet !== rec.sheet) continue;
      const dx = l.x - rec.x_mm, dy = l.y - rec.y_mm;
      const d = Math.hypot(dx, dy);
      if (d < bestDist && d < 800) { bestDist = d; best = l; }
    }
    if (best && !rec.label) rec.label = best.text;
  }
  return out;
}

function classifyDxfEntity(e) {
  const layer = (e.layer || '').toUpperCase();
  const t = (e.type || '').toUpperCase();
  if (t === 'TEXT' || t === 'MTEXT') return 'text';
  if (layer.includes('GRID')) return 'grid-bubble';
  if (layer.includes('OPEN') || layer.includes('PENETR') || layer.includes('SLEEVE')) return 'opening';
  if (layer.includes('BEAM') || layer.includes('BM') || layer.includes('GIRDER')) return 'beam';
  if (layer.includes('COL') || layer.includes('PILLAR')) return 'column';
  if (layer.includes('PIPE')) return 'pipe';
  if (layer.includes('DUCT')) return 'duct';
  if (layer.includes('EQUIP') || layer.includes('MECH')) return 'equipment';
  if (t === 'INSERT') return 'block';          // INSERT = block reference on most real-world DWGs
  if (t === 'BLOCK' || t === 'ENDBLK') return 'block';
  if (t === 'LINE' || t === 'LWPOLYLINE' || t === 'POLYLINE' || t === 'CIRCLE' || t === 'ARC') return 'line';
  return 'unknown';
}

function entityCentroid(e) {
  if (e.position) return { x: e.position.x, y: e.position.y };
  if (e.center) return { x: e.center.x, y: e.center.y };
  if (e.vertices && e.vertices.length) {
    let sx = 0, sy = 0;
    for (const v of e.vertices) { sx += v.x; sy += v.y; }
    return { x: sx / e.vertices.length, y: sy / e.vertices.length };
  }
  // LINE: midpoint of start/end
  if (typeof e.startPoint === 'object' && typeof e.endPoint === 'object') {
    return { x: (e.startPoint.x + e.endPoint.x) / 2, y: (e.startPoint.y + e.endPoint.y) / 2 };
  }
  // TEXT / INSERT / POINT / DIMENSION — only have startPoint
  if (e.startPoint) return { x: e.startPoint.x, y: e.startPoint.y };
  return null;
}

function entityDims(e) {
  if (e.vertices && e.vertices.length >= 2) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const v of e.vertices) {
      if (v.x < minX) minX = v.x; if (v.x > maxX) maxX = v.x;
      if (v.y < minY) minY = v.y; if (v.y > maxY) maxY = v.y;
    }
    return { w: maxX - minX, h: maxY - minY };
  }
  if (e.radius) return { w: e.radius * 2, h: e.radius * 2 };
  return { w: null, h: null };
}

function detectSheet(layer) {
  const m = /(\d{4})/.exec(layer);
  return m ? m[1] : 'default';
}

/* ============================================================
   DWG — magic-byte check + best-effort text sniff + libredwg conversion
   ============================================================ */
function parseDwg(buf, name, filePath) {
  const sig = buf.slice(0, 6).toString('ascii');
  const version = DWG_VERSIONS[sig];
  if (!version) {
    return {
      ok: false, kind: 'dwg', parseStatus: 'failed',
      error: `Unrecognized DWG magic bytes "${sig}". Expected AC1xxx version tag.`,
      parseMeta: { magicBytes: sig, recognized: false },
    };
  }
  // Best-effort ASCII extraction for layer names + labels (used as a hint even
  // when the full libredwg conversion succeeds)
  const ascii = buf.toString('binary');
  const layerRe = /[A-Z][A-Z0-9_\-]{2,30}/g;
  const layerCandidates = [...new Set(ascii.match(layerRe) || [])].slice(0, 40);
  const elevRe = /[EL\+\-LVL\.]{0,4}[\s]?[\+\-]?\d{1,2}\.\d{2,3}\s?m/gi;
  const elevations = [...new Set((ascii.match(elevRe) || []).map(s => s.trim()))].slice(0, 20);
  const pipeRe = /\b(?:DN|NPS|Ø)\s?\d{2,4}\b/g;
  const pipes = [...new Set((ascii.match(pipeRe) || []))].slice(0, 20);

  // ---- Try to do a REAL conversion via libredwg's dwg2dxf ----
  let fullParse = null;
  if (filePath) {
    try {
      const conv = convertDwgToDxf(filePath);
      if (!conv.ok) {
        console.error(`[dwg2dxf] ${name}: ${conv.error}`);
      } else {
        console.log(`[dwg2dxf] ${name}: converted OK via ${conv.dwg2dxfPath}, size=${conv.dxfBuf.length}`);
        fullParse = parseDxf(conv.dxfBuf, name);
        if (fullParse.ok) {
          console.log(`[dwg2dxf] ${name}: parsed ${fullParse.entityCount} entities, ${fullParse.layers.length} layers`);
          fullParse.parseMeta = {
            ...fullParse.parseMeta,
            kind: 'dwg',
            parseStatus: 'ok',
            dwgVersion: version,
            magicBytes: sig,
            layerCandidates,
            elevations,
            pipes,
            note: `Converted via dwg2dxf (${conv.dwg2dxfPath}); full DXF entity extraction applied.`,
            conversion: 'libredwg',
          };
          return fullParse;
        } else {
          console.error(`[dwg2dxf] ${name}: DXF parse failed: ${fullParse.error}`);
        }
      }
    } catch (e) {
      console.error(`[dwg2dxf] ${name}: exception ${e.message}`);
    }
  }

  return {
    ok: true, kind: 'dwg',
    parseStatus: 'partial',
    parseMeta: {
      magicBytes: sig,
      dwgVersion: version,
      sizeBytes: buf.length,
      layerCandidates,
      elevations,
      pipes,
      note: 'libredwg dwg2dxf not available; sent metadata to Gemini. Build libredwg to get full entity extraction.',
    },
    header: { dwgVersion: version },
  };
}

/* ============================================================
   IFC / PDF — stubs (return minimal metadata)
   ============================================================ */
function parseIfc(buf, name) {
  const ascii = buf.toString('utf8');
  const ifcClasses = [...new Set((ascii.match(/\bIFC[A-Z][A-Z0-9]+/g) || []))].slice(0, 20);
  return {
    ok: true, kind: 'ifc', parseStatus: 'partial',
    parseMeta: { sizeBytes: buf.length, ifcClasses },
  };
}
function parsePdfStub(name) {
  return {
    ok: false, kind: 'pdf', parseStatus: 'skipped',
    parseMeta: { note: 'PDF reference drawing — not parsed. Falls through to vision path.' },
  };
}

module.exports = { parseFile, dxfToEntities, classifyDxfEntity };
