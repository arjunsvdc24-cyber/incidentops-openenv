# IncidentOps - Production Docker Image
# Version: 15.0
#
# Build: docker build -t incidentops:15.0 .
# Run:   docker run -p 7860:7860 incidentops:15.0
# HuggingFace Spaces: automatically served at port 7860

FROM python:3.11-slim

# IMPORTANT: Set API keys at runtime via --build-arg or docker-compose.
# Do NOT commit API keys or secrets to the repository.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_TOKEN="" \
    OPENAI_API_KEY="" \
    GROQ_API_KEY="" \
    GEMINI_API_KEY="" \
    ASKME_API_KEY="" \
    LLM_PROVIDER="groq" \
    API_BASE_URL="https://api.groq.com/openai/v1" \
    MODEL_NAME="groq/llama-4-opus-17b" \
    DATABASE_URL="sqlite+aiosqlite:///./incidentops.db"

WORKDIR /app

# Install Node.js for building the React dashboard
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY dashboard/ ./dashboard/
COPY openenv.yaml .
COPY baseline.py .
COPY inference.py .
COPY README.md .
COPY pyproject.toml .
COPY .env.example .

# Build the React dashboard
WORKDIR /app/dashboard
RUN npm install && npm run build
WORKDIR /app

RUN mkdir -p /app/logs

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# uvicorn serves both the API and the React dashboard
# FastAPI main.py mounts dashboard/dist at /static and serves / at root
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
