#!/usr/bin/env python3
import sys
from hse.workers.surface_worker import run_surface_job

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: run_surface_worker.py <job_id> [subfolder]")
        sys.exit(1)

    job_id = sys.argv[1]
    subfolder = sys.argv[2] if len(sys.argv) > 2 else None

    run_surface_job(job_id, subfolder=subfolder)
