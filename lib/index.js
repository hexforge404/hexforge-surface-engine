const express = require("express");
const fs = require("fs");
const path = require("path");
const { v4: uuidv4 } = require("uuid");

const {
  nowIso,
  sanitizeSubfolder,
  buildJobStatus,
  writeJobManifest,
  readJobManifest,
  assertPublicPath,
  writeJsonAtomic
} = require("./lib/contracts");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Serve static assets. All public URLs must begin with /assets/
app.use("/assets", express.static(path.join(__dirname, "public/assets")));

// Root folders
const JOBS_ROOT = path.join(__dirname, "jobs");
const PUBLIC_SURFACE_ROOT = path.join(__dirname, "public/assets/surface");

// Ensure base dirs exist
fs.mkdirSync(JOBS_ROOT, { recursive: true });
fs.mkdirSync(PUBLIC_SURFACE_ROOT, { recursive: true });

/**
 * Helper: resolve jobDir and publicDir for a job.
 * Public is always: /assets/surface/<job_id>/...
 */
function getJobPaths(job_id) {
  const jobDir = path.join(JOBS_ROOT, job_id);
  const publicDir = path.join(PUBLIC_SURFACE_ROOT, job_id);
  const publicUrl = `/assets/surface/${job_id}/`;
  assertPublicPath(publicUrl);
  return { jobDir, publicDir, publicUrl };
}



/**
 * Minimal "engine" runner placeholder.
 * Replace this with your real surface generation pipeline.
 *
 * This demo:
 * - marks running
 * - waits briefly
 * - writes a tiny placeholder artifact
 * - marks complete
 */
async function runJob(job_id) {
  const { jobDir, publicDir, publicUrl } = getJobPaths(job_id);
  const manifest = readJobManifest(jobDir);
  if (!manifest) return;

  // mark running
  manifest.status = "running";
  manifest.updated_at = nowIso();
  writeJobManifest(jobDir, manifest);

  // simulate work
  await new Promise((r) => setTimeout(r, 500));

  // create a placeholder artifact
  fs.mkdirSync(publicDir, { recursive: true });
  const artifactName = "preview.txt";
  const artifactPath = path.join(publicDir, artifactName);
  fs.writeFileSync(artifactPath, `Surface v1 placeholder for job ${job_id}\n`, "utf8");

  // update manifest: complete + public outputs
  manifest.status = "complete";
  manifest.updated_at = nowIso();
  manifest.public_root = publicUrl;
  manifest.public = {
    preview: `${publicUrl}${artifactName}`,
    manifest: `${publicUrl}job_manifest.json`
  };

  // Also publish a copy of manifest to public dir (so consumers can fetch it)
  const publicManifestPath = path.join(publicDir, "job_manifest.json");
  writeJsonAtomic(publicManifestPath, manifest);

  // write authoritative manifest to job dir
  writeJobManifest(jobDir, manifest);
}

/**
 * POST /api/surface/jobs
 * Creates a job and returns a job_status envelope.
 */
app.post("/api/surface/jobs", async (req, res) => {
  try {
    const job_id = uuidv4();

    // Optional subfolder support (stored in manifest, but does not change public root for v1)
    // If you truly use subfolder in v1 public paths, incorporate it ONLY via this function.
    const requestedSubfolder = sanitizeSubfolder(req.body?.subfolder ?? null);

    const { jobDir, publicDir, publicUrl } = getJobPaths(job_id);

    // Create dirs
    fs.mkdirSync(jobDir, { recursive: true });
    fs.mkdirSync(publicDir, { recursive: true });

    // Snapshot request (optional but useful)
    const jobRequestSnapshot = {
      received_at: nowIso(),
      body: req.body ?? {}
    };
    writeJsonAtomic(path.join(jobDir, "job.json"), jobRequestSnapshot);

    // Authoritative manifest (required)
    const created_at = nowIso();
    const manifest = {
      job_id,
      service: "hexforge-glyphengine",
      created_at,
      updated_at: created_at,
      status: "queued",
      request: req.body ?? {},
      subfolder: requestedSubfolder,
      public_root: publicUrl,
      public: {
        manifest: `${publicUrl}job_manifest.json`
      }
    };

    // Write job manifest to job folder
    writeJobManifest(jobDir, manifest);

    // Also publish a copy to public dir immediately (so consumers can fetch it even while queued)
    writeJsonAtomic(path.join(publicDir, "job_manifest.json"), manifest);

    // Return contract-clean job_status envelope
    const statusEnvelope = buildJobStatus({
      job_id,
      status: "queued",
      updated_at: created_at,
      result: { public: publicUrl }
    });

    // Fire-and-forget job runner
    runJob(job_id).catch((err) => {
      try {
        const m = readJobManifest(jobDir);
        if (m) {
          m.status = "failed";
          m.updated_at = nowIso();
          m.error = { message: String(err?.message || err) };
          writeJobManifest(jobDir, m);
          writeJsonAtomic(path.join(publicDir, "job_manifest.json"), m);
        }
      } catch (_) {}
      console.error("[glyphengine] job failed:", err);
    });

    return res.status(201).json(statusEnvelope);
  } catch (err) {
    console.error(err);
    return res.status(400).json({
      error: "Bad Request",
      message: String(err?.message || err)
    });
  }
});

/**
 * GET /api/surface/jobs/:job_id
 * Returns job_status envelope derived from manifest (authoritative).
 */
app.get("/api/surface/jobs/:job_id", (req, res) => {
  try {
    const job_id = String(req.params.job_id || "").trim();
    if (!job_id) return res.status(400).json({ error: "job_id required" });

    const { jobDir, publicUrl } = getJobPaths(job_id);
    const manifest = readJobManifest(jobDir);
    if (!manifest) return res.status(404).json({ error: "not found" });

    const env = buildJobStatus({
      job_id,
      status: manifest.status,
      updated_at: manifest.updated_at,
      result: { public: publicUrl }
    });

    // Only attach more details when complete/failed (optional)
    if (manifest.status === "complete" || manifest.status === "failed") {
      env.result = env.result || {};
      env.result.manifest = `${publicUrl}job_manifest.json`;
      assertPublicPath(env.result.manifest);
    }

    return res.json(env);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "internal", message: String(err?.message || err) });
  }
});

/**
 * Health (optional, harmless)
 */
app.get("/health", (_req, res) => res.json({ ok: true, service: "hexforge-glyphengine" }));

app.listen(PORT, () => {
  console.log(`[glyphengine] listening on :${PORT}`);
});
