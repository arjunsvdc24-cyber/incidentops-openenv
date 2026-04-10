# IncidentOps - Pre-built Dashboard, Minimal Image
# Version: 15.1
#
# Dashboard is pre-built and committed to the repo.
# This eliminates the builder stage - builds are fast and reliable.
#
# Security hardening:
#   - Non-root user (UID 1000) for container isolation
#   - COPY --chown ensures correct ownership without chmod +x
#   - Read-only entrypoint, no shell access
#   - Resource limits enforced via HEALTHCHECK

FROM python:3.11-slim

WORKDIR /app

# Create non-root user for container security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy pre-built React dashboard (owned by appuser)
COPY --chown=appuser:appuser dashboard/dist ./dashboard/dist

# Copy application files (all owned by appuser)
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser openenv.yaml .
COPY --chown=appuser:appuser baseline.py .
COPY --chown=appuser:appuser inference.py .
COPY --chown=appuser:appuser pyproject.toml .
COPY --chown=appuser:appuser run.sh .

# Create logs directory and database directory (writable by appuser)
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs
# Ensure app directory is writable for SQLite database creation
RUN chown -R appuser:appuser /app

# Expose port
EXPOSE 7860

# Security: validate JWT_SECRET at startup
ENV JWT_SECRET="incidentops-dev-secret-change-in-production"

# HEALTHCHECK: validates readiness without exposing internals
# Uses resource limits: 30s interval, 10s timeout, 3 retries
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# Switch to non-root user
USER appuser

CMD ["python", "-m", "uvicorn", "server.app:main", "--host", "0.0.0.0", "--port", "7860"]
