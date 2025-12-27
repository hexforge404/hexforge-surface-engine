// lib/contract_adapter.js
// Contract adapters for Surface v1:
// - job_status envelope responses
// - job_manifest.json (v1) writer
//
// Goal: smallest correct change wins.
// We DO NOT change job generation logic; we only normalize outputs + write manifest.

const fs = require("fs");
const path = require("path");

const SERVICE = "hexforge-glyphengine";

function nowIso() {
  return new Date().toISOString();
}

function ensureAssetsPath(p) {
  if (typeof p !== "string" || !p.startsWith("/assets/")) {
    throw new Error(`public path must start with /assets/ (got: ${JSON.stringify(p)})`);
  }
  return p;
}

function derivePublicRootFromPublicMap(publicMap) {
  // Expect something like:
  // public.job = "/assets/surface/<job_id>/job.json"
  const jobPath = publicMap && publicMap.job;
  if (typeof jobPath === "string") {
    return jobPath.replace(/\/job\.json$/, "/");
  }
  return null;
}

function inferStatusFromDisk(jobDirAbs) {
  // Minimal inference:
  // complete if hero exists, running if job.json exists, queued otherwise
  try {
    if (fs.existsSync(path.join(jobDirAbs, "previews", "hero.png"))) return "complete";
    if (fs.existsSync(path.join(jobDirAbs, "job.json"))) return "running";
  } catch (_) {}
  return "queued";
}

function jobStatusEnvelope({ job_id, status, public_root, updated_at, extra }) {
  const out = {
    job_id,
    status,
    service: SERVICE,
    updated_at: updated_at || nowIso(),
  };
  if (public_root) {
    out.result = { public: ensureAssetsPath(public_root) };
  }
  if (extra && typeof extra === "object") {
    Object.assign(out, extra);
  }
  return out;
}

function writeJobManifestV1({ jobDirAbs, job_id, subfolder, status, public_root, public_map }) {
  const createdAt = nowIso();
  const updatedAt = createdAt;

  const pr = ensureAssetsPath(public_root);
  const publicClean = {};
  if (public_map && typeof public_map === "object") {
    for (const [k, v] of Object.entries(public_map)) {
      if (typeof v === "string") publicClean[k] = ensureAssetsPath(v);
    }
  }

  const doc = {
    job_id,
    service: SERVICE,
    subfolder: subfolder ?? null,
    status,
    created_at: createdAt,
    updated_at: updatedAt,
    public_root: pr,
    public: publicClean,
  };

  fs.mkdirSync(jobDirAbs, { recursive: true });

  const outPath = path.join(jobDirAbs, "job_manifest.json");
  const tmpPath = outPath + ".tmp";
  fs.writeFileSync(tmpPath, JSON.stringify(doc, null, 2));
  fs.renameSync(tmpPath, outPath);

  return outPath;
}

module.exports = {
  SERVICE,
  nowIso,
  ensureAssetsPath,
  derivePublicRootFromPublicMap,
  inferStatusFromDisk,
  jobStatusEnvelope,
  writeJobManifestV1,
};
