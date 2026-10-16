// lib/upload.js — multer config + SHA-256 hashing + file storage
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const multer = require('multer');

const DATA_DIR = process.env.DATA_DIR || './data';
const UPLOADS_DIR = path.join(DATA_DIR, 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const ALLOWED_EXTS = new Set(['.dwg', '.dxf', '.ifc', '.pdf']);
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

const storage = multer.memoryStorage();

const upload = multer({
  storage,
  limits: { fileSize: MAX_FILE_SIZE, files: 3 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase();
    if (!ALLOWED_EXTS.has(ext)) {
      return cb(new MulterError(415, `Unsupported file type "${ext}". Allowed: ${[...ALLOWED_EXTS].join(', ')}`));
    }
    cb(null, true);
  },
});

// multer's own error class — we wrap foreign errors into this for HTTP mapping
class MulterError extends Error {
  constructor(httpStatus, msg) {
    super(msg);
    this.name = 'MulterError';
    this.httpStatus = httpStatus;
  }
}

function ensureProjectDir(projectId) {
  const dir = path.join(UPLOADS_DIR, projectId);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/** Persist a memory-storage file to disk under uploads/<projectId>/<discipline>.<ext> */
function persistUpload(fileBuffer, projectId, discipline, originalName) {
  const ext = path.extname(originalName || '').toLowerCase() || '.bin';
  const dir = ensureProjectDir(projectId);
  const filename = `${discipline}${ext}`;
  const fullPath = path.join(dir, filename);
  fs.writeFileSync(fullPath, fileBuffer);
  return {
    storedPath: path.relative(DATA_DIR, fullPath),
    fullPath,
    sha256: sha256(fileBuffer),
    sizeBytes: fileBuffer.length,
    format: ext.slice(1),
  };
}

module.exports = {
  upload,
  MulterError,
  sha256,
  persistUpload,
  ALLOWED_EXTS,
  MAX_FILE_SIZE,
  UPLOADS_DIR,
  DATA_DIR,
};
