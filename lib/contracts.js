// lib/contracts.js
const fs = require("fs");
const path = require("path");

const SERVICE = "hexforge-glyphengine";

function nowIso() {
  return new Date().toISOString();
}

function sanitizeSubfolder(value) {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  if (!s) return null;
  // allow a-z A-Z 0-9 _ - /
  if (!/^[a-zA-Z0-9/_-]+$/.test(s)) {
    throw new Error("Invalid subfolder (allowed: a-zA-Z0-9/_-)");
  }
  if (s.includes("..")) {
    throw new Error("Invalid subfolder (path traversal)");
  }
  return s;
}

function assertPublicPath(p) {
  if (typeof p !== "string" || !p.startsWith("/assets/")) {
    throw new Error(`Public URL must start with /assets/ (got: ${JSON.stringify(p)})`);
  }
}

function buildJobStatus({ job_id, status, updated_at, result }) {
  if (!job_id) throw new Error("job_id required");
  if (!status) throw new Error("status required");
  const env = {
    job_id,
    status,
    service: SERVICE,
    updated_at: updated_at || nowIso(),
  };
  if (result) env.result = result;
  // validate result.public if present
  if (env.result && env.result.public) assertPublicPath(env.result.public);
  return env;
}

function writeJsonAtomic(filePath, obj) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = filePath + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), "utf8");
  fs.renameSync(tmp, filePath);
}

function writeJobManifest(jobDir, manifest) {
  fs.mkdirSync(jobDir, { recursive: true });
  const p = path.join(jobDir, "job_manifest.json");
  writeJsonAtomic(p, manifest);
  return p;
}

function readJobManifest(jobDir) {
  const p = path.join(jobDir, "job_manifest.json");
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

module.exports = {
  nowIso,
  sanitizeSubfolder,
  buildJobStatus,
  writeJobManifest,
  readJobManifest,
  assertPublicPath,
  writeJsonAtomic,
};
