# === BUILD STAGE ===
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === PRODUCTION STAGE ===
FROM python:3.11-slim

# Security: Don't run as root
RUN groupadd -r mycukai && useradd -r -g mycukai -d /app -s /sbin/nologin mycukai

WORKDIR /app

# Install only runtime dependencies (no gcc, no build tools in production)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=mycukai:mycukai . .

# Security: Remove unnecessary files from image
RUN rm -rf .git .env .env.* tests/ *.md \
    && find . -name "*.pyc" -delete \
    && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Security: Create data directories with proper permissions
RUN mkdir -p data/raw data/processed data/embeddings data/learning data/security \
    && chown -R mycukai:mycukai data/

# Security: Make filesystem read-only where possible
RUN chmod -R 555 /app/*.py /app/bot/ /app/api/ /app/scraper/ /app/processor/ /app/embedder/ /app/agent/ /app/security/ /app/monitoring/ 2>/dev/null || true
RUN chmod -R 755 /app/data/

# Security: Drop all capabilities, run as non-root
USER mycukai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Security: No shell access in production
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-concurrency", "50", "--timeout-keep-alive", "5"]
