# IncidentOps Troubleshooting Guide

Common issues, diagnosis steps, and quick fixes.

---

## JWT_SECRET Not Set

**Symptom**: Server fails to start with `RuntimeError: JWT_SECRET environment variable not set`.

**Quick Fix**:
```bash
# Option 1: Set environment variable
export JWT_SECRET="incidentops-dev-secret-change-in-production"

# Option 2: In Docker
docker run -p 7860:7860 \
  -e JWT_SECRET="your-secure-secret-here" \
  ghcr.io/incidentops/incidentops:latest
```

**Production**:
```bash
# Generate a secure random secret
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
```

---

## Docker Build Fails

**Symptom**: `docker build` fails with missing dependencies or module import errors.

**Diagnosis**:
```bash
# Check requirements.txt exists
ls requirements.txt

# Verify Python version
python --version  # Should be 3.11

# Test dependency installation locally
pip install -r requirements.txt
```

**Quick Fix**:
```bash
# Clean Docker build cache
docker build --no-cache -t incidentops:local .

# Or rebuild with explicit platform
docker build --platform linux/amd64 -t incidentops:local .
```

**Common Causes**:
- Missing `dashboard/dist/` — run `cd dashboard && npm install && npm run build`
- Python version mismatch — ensure 3.11
- Platform-specific binary (bcrypt on Windows) — use Python 3.11-slim base

---

## OpenAI API Key Not Found

**Symptom**: `/baseline` or `/openai/check` returns authentication error.

**Diagnosis**:
```bash
# Check if API key is set
echo $OPENAI_API_KEY  # Linux/macOS
echo %OPENAI_API_KEY% # Windows CMD
$env:OPENAI_API_KEY   # Windows PowerShell

# Test API key validity
curl -X POST http://localhost:7860/openai/check \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-key-here"}'
```

**Quick Fix**:
```bash
# Set before starting server
export OPENAI_API_KEY=sk-...

# Or pass in request body
curl -X POST http://localhost:7860/baseline \
  -H "Content-Type: application/json" \
  -d '{"seed": 42, "use_llm": true, "api_key": "sk-..."}'
```

**Note**: IncidentOps works fully without an API key — the rule-based baseline is always available.

---

## Dashboard Blank / Not Loading

**Symptom**: Visit `http://localhost:7860` shows blank page or 404.

**Diagnosis**:
```bash
# Check health first
curl http://localhost:7860/health

# Check if static files exist
ls dashboard/dist/index.html
```

**Quick Fix**:
```bash
# Rebuild dashboard
cd dashboard
npm install
npm run build

# Restart server
python -m app.main
```

**Docker Users**:
```bash
# Ensure pre-built dist is in image
docker run -p 7860:7860 ghcr.io/incidentops/incidentops:latest

# If using local build, verify dist exists
ls dashboard/dist/
```

---

## Validation Tests Failing

**Symptom**: `/validation` returns failures or `pytest` reports test errors.

**Diagnosis**:
```bash
# Run validation suite
curl http://localhost:7860/validation

# Or run tests directly
pytest tests/ -v
```

**Common Fixes**:

1. **Missing dependencies**:
```bash
pip install -r requirements.txt
```

2. **Database locked** (SQLite on Windows):
```bash
# Kill any existing Python processes
taskkill /F /IM python.exe  # Windows
pkill -f "python.*app.main"  # Linux/macOS
```

3. **Determinism check fails**:
```bash
curl http://localhost:7860/determinism/check
# Should return {"status": "ok", "deterministic": true}
```

---

## PyO3 / bcrypt Import Error

**Symptom**: `ImportError: cannot import name 'bcrypt'` during test run.

**Quick Fix**:
```bash
# Reinstall bcrypt
pip uninstall bcrypt -y
pip install bcrypt

# Or use pure-Python fallback
pip install bcrypt --only-binary=:all:
```

**Windows Users**:
```bash
# Install Visual C++ Build Tools or use conda
conda install bcrypt
```

---

## Episodes Not Saving

**Symptom**: Episodes created via `/reset` + `/step` not appearing in `/episodes`.

**Explanation**: Episodes from API calls are in-memory only. To persist:

**Quick Fix**:
```bash
# Save episode after completion
curl -X POST http://localhost:7860/episodes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "task_id": "oom_crash",
    "score": 0.85,
    "trajectory": [...],
    "metadata": {}
  }'
```

**Register/Login First**:
```bash
curl -X POST http://localhost:7860/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

---

## WebSocket Connection Failed

**Symptom**: Browser console shows `WebSocket connection failed` at `/ws`.

**Diagnosis**:
```bash
# Test WebSocket manually
curl -i \
  -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:7860/ws
```

**Quick Fix**:
- Ensure server is not behind a proxy blocking WebSocket upgrades
- Check firewall rules allow port 7860
- If behind nginx, add WebSocket proxy headers:
```nginx
location /ws {
    proxy_pass http://localhost:7860;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## Performance Issues / Slow Responses

**Diagnosis**:
```bash
# Check Prometheus metrics
curl http://localhost:7860/metrics | grep -E "(request_latency|active_websockets)"

# Check database size
ls -lh incidentops.db
```

**Quick Fixes**:

1. **Clear old episodes**:
```bash
# Via API (requires auth)
curl -X DELETE http://localhost:7860/episodes/cleanup \
  -H "Authorization: Bearer <admin-token>"
```

2. **Restart with fresh database**:
```bash
rm incidentops.db
python -m app.main
```

3. **Limit concurrent WebSocket connections**:
```bash
# Set max connections via environment
export MAX_WS_CONNECTIONS=100
python -m app.main
```

---

## HuggingFace Space Build Timeout

**Symptom**: HF Space build times out or shows "Build started" but never completes.

**Quick Fix**:
```bash
# 1. Ensure dashboard/dist/ is committed (not in .gitignore)
git add dashboard/dist/
git commit -m "chore: pre-built dashboard"

# 2. Push to trigger rebuild
git push origin main

# 3. Check build logs at https://huggingface.co/spaces/YOUR_SPACE/settings
```

**If Still Failing**:
- Reduce image size: `docker build` without dev dependencies
- Pre-build all assets before commit
- Check `.dockerignore` is not excluding `app/` or `openenv.yaml`

---

## Port Already in Use

**Symptom**: `OSError: [Errno 98] Address already in use` or similar.

**Quick Fix**:
```bash
# Find process using port 7860
lsof -i :7860        # macOS/Linux
netstat -ano | findstr :7860  # Windows

# Kill the process
kill -9 <PID>        # macOS/Linux
taskkill /F /PID <PID>  # Windows

# Or use a different port
python -m app.main --port 7861
```

---

## Need More Help?

1. **Check the API docs**: Visit `http://localhost:7860/docs`
2. **Run validation**: Visit `http://localhost:7860/validation`
3. **Check health**: `curl http://localhost:7860/health`
4. **Review logs**: Server outputs to stdout — check terminal for errors
5. **GitHub issues**: Report bugs at https://github.com/incidentops/environment/issues
