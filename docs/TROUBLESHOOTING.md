# Troubleshooting Guide

This guide covers common issues encountered when running or deploying IncidentOps.

## Dashboard Shows Blank Page

**Symptom**: Loading `http://localhost:7860/` shows a blank page or a "Dashboard not found" message.

**Diagnosis**:
1. Check if the pre-built dashboard exists:
   ```bash
   ls dashboard/dist/index.html
   ```
2. Check the server `/health` endpoint:
   ```bash
   curl http://localhost:7860/health
   ```

**Resolution**:
- If the file is missing, rebuild the dashboard:
  ```bash
  cd dashboard && npm install && npm run build
  ```
- If the server is not responding, check logs for port conflicts:
  ```bash
  lsof -i :7860  # macOS/Linux
  netstat -ano | findstr :7860  # Windows
  ```
- If using Docker and the static files are not mounting correctly:
  ```bash
  docker run -v $(pwd)/dashboard/dist:/app/dashboard/dist ...
  ```

---

## OpenAI API Errors

**Symptom**: LLM baseline (`use_llm: true`) returns errors like `AuthenticationError`, `RateLimitError`, or `APIConnectionError`.

**Diagnosis**:
1. Verify the API key is set:
   ```bash
   echo $GROQ_API_KEY  # or OPENAI_API_KEY, GEMINI_API_KEY, etc.
   ```
2. Test connectivity:
   ```bash
   curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models
   ```

**Resolution**:
- Set the API key in your environment before starting the server:
  ```bash
  export GROQ_API_KEY="gsk_..."
  python -m uvicorn app.main:app --port 7860
  ```
- Or pass it in the request body (for one-off evaluation):
  ```json
  {"use_llm": true, "groq_api_key": "gsk_...", "seed": 42}
  ```
- If using Groq, check [Groq API rate limits](https://console.groq.com/docs/rate-limits) — free tier has strict limits
- If using HuggingFace Inference API, ensure your token has the proper scopes:
  ```bash
  export HF_TOKEN="hf_..."
  ```

---

## Tests Fail with PyO3 / bcrypt Error

**Symptom**: Running `pytest` fails with errors like `PyO3` or `ImportError: cannot import name 'bcrypt'`.

**Cause**: The `bcrypt` package includes Rust extension modules that can fail on Windows or mismatched Python versions. The fix is to use a lazy import so bcrypt is only loaded when password operations are needed.

**Resolution**:
- Install bcrypt explicitly:
  ```bash
  pip install bcrypt
  ```
- If using a virtual environment, ensure it is activated:
  ```bash
  python -m venv venv
  source venv/bin/activate  # Linux/macOS
  venv\Scripts\activate   # Windows
  pip install -r requirements.txt
  ```
- If the error persists on Windows, try the pure-Python fallback:
  ```bash
  pip install bcrypt --only-binary=:all:
  ```
- IncidentOps v15.1 uses lazy imports for bcrypt in `app/db/repositories.py` — ensure you have the latest version

---

## HuggingFace Space Won't Build

**Symptom**: HF Space build fails with errors about missing files, module import failures, or Docker timeout.

**Diagnosis**:
1. Check that `openenv.yaml` exists and is valid:
   ```bash
   python -c "import yaml; yaml.safe_load(open('openenv.yaml'))"
   ```
2. Check that `dashboard/dist/` is committed to the repo:
   ```bash
   ls dashboard/dist/index.html
   ```
3. Check `.dockerignore` is not excluding needed files:
   ```bash
   cat .dockerignore
   ```

**Resolution**:
- The `dashboard/dist/` directory must be pre-built and committed — the Docker image does not run `npm build`
- If you recently modified the dashboard, rebuild and commit:
  ```bash
  cd dashboard && npm run build && cd ..
  git add dashboard/dist/
  git commit -m "chore: rebuild dashboard"
  ```
- Check the HF Space logs at `https://huggingface.co/spaces/<your-space>/settings` for the actual build error
- Ensure `requirements.txt` pins compatible versions — HF Spaces uses a frozen Python environment

---

## JWT Authentication Failures

**Symptom**: `/auth/login` returns a valid token but subsequent requests with that token return 401.

**Diagnosis**:
1. Check that `JWT_SECRET` is set and consistent across restarts:
   ```bash
   python -c "from app.main import JWT_SECRET; print(JWT_SECRET)"
   ```
2. Check token expiration — tokens expire after 7 days

**Resolution**:
- Set `JWT_SECRET` to a secure value before starting:
  ```bash
  export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
  python -m uvicorn app.main:app --port 7860
  ```
- IncidentOps v15.1 enforces that `JWT_SECRET` is set — the server will refuse to start without it

---

## Episode Replay is Empty or Incomplete

**Symptom**: `/episodes/{id}/replay` returns an empty trajectory or missing steps.

**Diagnosis**:
1. Check the episode exists:
   ```bash
   curl http://localhost:7860/episodes/{id}
   ```
2. Check if `trajectory` was saved when the episode was recorded

**Resolution**:
- Trajectories must be explicitly saved by the client after an episode completes via `POST /episodes`
- Only episodes saved through the API are persisted; in-memory episodes from `/reset` + `/step` are lost on restart

---

## Prometheus Metrics Not Visible in Grafana

**Symptom**: Grafana dashboard shows "No data" for all panels.

**Diagnosis**:
1. Check `/metrics` endpoint returns data:
   ```bash
   curl http://localhost:7860/metrics | head -20
   ```
2. Check Prometheus data source in Grafana is pointing to the correct URL

**Resolution**:
- Prometheus must be configured to scrape the IncidentOps `/metrics` endpoint
- In `grafana/prometheus.yml`, ensure the target matches your deployment:
  ```yaml
  scrape_configs:
    - job_name: 'incidentops'
      static_configs:
        - targets: ['localhost:7860']  # or your container IP
  ```
- If using Docker Compose, use the service name: `http://incidentops:7860`

---

## Version Mismatch Between API and openenv.yaml

**Symptom**: OpenEnv validation harness reports schema mismatch errors.

**Resolution**:
- Ensure `openenv.yaml` reflects the actual observation output exactly:
  ```bash
  python -c "
  from app.environment import make_env
  env = make_env(seed=42)
  obs = env.reset(seed=42)
  print(list(obs.keys()))
  # Compare with openenv.yaml observation schema
  "
  ```
- The schema in `openenv.yaml` is generated from the actual Pydantic model fields — if you add a new field to the environment, update both the model and the YAML schema
