FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps:
# - curl for healthchecks/debug
# - Pillow runtime deps (safe defaults)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libjpeg62-turbo \
    zlib1g \
    libpng16-16 \
    libfreetype6 \
 && rm -rf /var/lib/apt/lists/*


# Create non-root user (matches your compose user: 10001)
RUN useradd -m -u 10001 -s /bin/bash appuser

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/hse /app/hse
COPY scripts /app/scripts


# (Optional) if you ever write temp stuff under /app, this avoids surprises
RUN chown -R appuser:appuser /app

EXPOSE 8092

USER appuser

# IMPORTANT: umask 0002 so outputs in setgid dirs are group-writable
CMD ["sh", "-lc", "umask 0002 && exec uvicorn hse.main:app --host 0.0.0.0 --port 8092"]
