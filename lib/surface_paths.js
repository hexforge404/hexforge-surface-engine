// lib/surface_paths.js
const path = require("path");

// MUST match your container volume path (you confirmed this exists):
// /data/hexforge3d/surface/<job_id>/...
const SURFACE_ROOT = "/data/hexforge3d/surface";

function jobDirAbs(job_id) {
  return path.join(SURFACE_ROOT, job_id);
}

module.exports = {
  SURFACE_ROOT,
  jobDirAbs,
};
