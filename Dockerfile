# IncidentOps - Optimized Multi-Stage Docker Image
# Version: 15.0
#
# Build: DOCKER_BUILDKIT=1 docker build -t incidentops:15.0 .
# Run:   docker run -p 7860:7860 incidentops:15.0

# ============================================================
# Stage 1: Builder - Install deps and build React dashboard
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install Node.js for building the React dashboard
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies FIRST (better cache hit)
# Only re-installs when requirements.txt changes, not code changes
COPY requirements.txt .

# Use BuildKit cache mount for pip caching (faster rebuilds)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy application files (after deps installed for better caching)
COPY app/ ./app/
COPY dashboard/ ./dashboard/

# Build the React dashboard
WORKDIR /app/dashboard
RUN npm ci --prefer-offline && npm run build

# ============================================================
# Stage 2: Production - Minimal runtime image
# ============================================================
FROM python:3.11-slim AS production

# Set non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install only runtime dependencies (no npm/node in final image)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user -r requirements.txt

# Copy built React dashboard from builder stage
COPY --from=builder /app/dashboard/dist ./app/static

# Copy application files
COPY app/ ./app/
COPY openenv.yaml .
COPY baseline.py .
COPY inference.py .
COPY pyproject.toml .
COPY .env.example .

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for FastAPI/uvicorn
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# uvicorn serves both the API and the React dashboard
# FastAPI main.py mounts dashboard/dist at /static and serves / at root
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]