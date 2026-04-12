# Hackathon Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt the `incidentops` RL environment to meet the automated validation and evaluation requirements of the OpenEnv hackathon.

**Architecture:** We will modify the existing `LLMBaselineAgent` to read specific environment variables required by the hackathon evaluator, create a top-level `inference.py` script that acts as the entry point, and update the FastAPI `/baseline` endpoint to correctly handle these new variables.

**Tech Stack:** Python, FastAPI, OpenAI Client

---

### Task 1: Update `LLMBaselineAgent` configuration

**Files:**
- Modify: `app/llm_baseline.py`

- [ ] **Step 1: Modify imports and `LLMAgentConfig`**
Update the model default in `LLMAgentConfig` and add a check for the environment variables.

Modify `LLMAgentConfig`:
```python
@dataclass
class LLMAgentConfig:
    """Configuration for LLM agent"""
    seed: int = 42
    model: str = os.environ.get("MODEL_NAME", "gpt-4o")
    max_tokens: int = 500
    temperature: float = 0.0  # Deterministic
    max_steps: int = 20
```

- [ ] **Step 2: Update LLMBaselineAgent client initialization**
Change `api_key` and add `base_url`.

Modify `__init__` in `LLMBaselineAgent`:
```python
    def __init__(self, config: Optional[LLMAgentConfig] = None):
        self.config = config or LLMAgentConfig()
        self.rng = random.Random(self.config.seed)

        # Initialize OpenAI client
        self.client = None
        self.api_key = os.environ.get("HF_TOKEN")
        self.base_url = os.environ.get("API_BASE_URL")

        if HAS_OPENAI and self.api_key and self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
```

- [ ] **Step 3: Update `check_openai_available`**
Update the availability check to look for the new environment variables.

Modify `check_openai_available`:
```python
def check_openai_available() -> bool:
    """Check if OpenAI API is available via hackathon env vars"""
    return HAS_OPENAI and os.environ.get("HF_TOKEN") is not None and os.environ.get("API_BASE_URL") is not None
```

- [ ] **Step 4: Commit**
```bash
git add app/llm_baseline.py
git commit -m "feat: update llm_baseline to use hackathon env vars"
```

### Task 2: Create `inference.py`

**Files:**
- Create: `inference.py`

- [ ] **Step 1: Create the inference script**
Write the following code to `inference.py` at the root directory:

```python
#!/usr/bin/env python3
"""
IncidentOps - Hackathon Inference Script

Runs the baseline LLM evaluation using the OpenAI client configured
via API_BASE_URL, MODEL_NAME, and HF_TOKEN.
"""
import os
import sys
import json

def check_env_vars():
    """Verify required hackathon environment variables exist."""
    missing = []
    if not os.environ.get("API_BASE_URL"):
        missing.append("API_BASE_URL")
    if not os.environ.get("MODEL_NAME"):
        missing.append("MODEL_NAME")
    if not os.environ.get("HF_TOKEN"):
        missing.append("HF_TOKEN")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

def main():
    check_env_vars()

    print("Running IncidentOps LLM Baseline Evaluation...")

    from app.llm_baseline import run_llm_evaluation, check_openai_available

    if not check_openai_available():
        print("Error: OpenAI client could not be initialized. Check dependencies and credentials.", file=sys.stderr)
        sys.exit(1)

    results = run_llm_evaluation(
        seed=42,
        max_steps=20,
        verbose=True
    )

    print("\n" + "="*50)
    print("FINAL RESULTS JSON:")
    print(json.dumps(results, indent=2))
    print("="*50)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make the script executable**
```bash
chmod +x inference.py
```

- [ ] **Step 3: Commit**
```bash
git add inference.py
git commit -m "feat: add root inference.py script for automated evaluation"
```

### Task 3: Update `app/main.py` endpoints

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Update `BaselineRequest` model**
Modify the request model to accept the new optional credentials.

Modify `BaselineRequest`:
```python
class BaselineRequest(BaseModel):
    seed: int = 42
    max_steps: int = 20
    verbose: bool = False
    use_llm: bool = True
    hf_token: Optional[str] = None
    api_base_url: Optional[str] = None
    model_name: Optional[str] = None
```

- [ ] **Step 2: Update `/baseline` endpoint logic**
Modify the logic that overrides environment variables for the LLM evaluation.

Modify `run_baseline` endpoint:
```python
@app.post("/baseline")
async def run_baseline(request: BaselineRequest):
    """Run baseline agent evaluation for easy, medium, hard difficulties"""
    try:
        if request.use_llm:
            from app.llm_baseline import run_llm_evaluation, check_openai_available
            import os

            # Allow runtime API variables from request
            env_vars_set = []
            if request.hf_token:
                os.environ["HF_TOKEN"] = request.hf_token
                env_vars_set.append("HF_TOKEN")
            if request.api_base_url:
                os.environ["API_BASE_URL"] = request.api_base_url
                env_vars_set.append("API_BASE_URL")
            if request.model_name:
                os.environ["MODEL_NAME"] = request.model_name
                env_vars_set.append("MODEL_NAME")

            try:
                if check_openai_available():
                    results = run_llm_evaluation(
                        seed=request.seed,
                        max_steps=request.max_steps,
                        verbose=request.verbose
                    )
                    return {
                        "easy": results["easy"],
                        "medium": results["medium"],
                        "hard": results["hard"],
                        "total": results["total"],
                        "agent_type": "llm",
                        "success": True,
                    }
                else:
                    return {
                        "error": "Required API variables not set. Provide hf_token and api_base_url or set env vars.",
                        "success": False,
                        "fallback": "rule_based",
                    }
            finally:
                for var in env_vars_set:
                    os.environ.pop(var, None)
```

- [ ] **Step 3: Update `OpenAICheckRequest` and endpoint (optional but cleaner)**
Rename to match the new paradigm in `app/main.py`.

Modify `OpenAICheckRequest` and `/openai/check` (lines ~592-624):
```python
class OpenAICheckRequest(BaseModel):
    hf_token: str
    api_base_url: str
    model_name: Optional[str] = None

@app.post("/openai/check")
async def check_openai_key(request: OpenAICheckRequest):
    """Verify an OpenAI API client works with given base_url and token"""
    try:
        import os
        os.environ["HF_TOKEN"] = request.hf_token
        os.environ["API_BASE_URL"] = request.api_base_url
        if request.model_name:
            os.environ["MODEL_NAME"] = request.model_name

        try:
            from openai import OpenAI
            client = OpenAI(api_key=request.hf_token, base_url=request.api_base_url)
            models = client.models.list()
            model_ids = [m.id for m in models.data[:5]]
            return {
                "valid": True,
                "models_available": model_ids,
                "message": "API configuration is valid",
            }
        except Exception as e:
            return {
                "valid": False,
                "message": str(e),
            }
        finally:
            os.environ.pop("HF_TOKEN", None)
            os.environ.pop("API_BASE_URL", None)
            if request.model_name:
                os.environ.pop("MODEL_NAME", None)
    except ImportError:
        return {
            "valid": False,
            "message": "openai package not installed",
        }
```

- [ ] **Step 4: Commit**
```bash
git add app/main.py
git commit -m "feat: update /baseline and /openai/check endpoints for new env vars"
```

### Task 4: Local verification

- [ ] **Step 1: Test the inference script**
Set mock variables and verify it throws expected errors (since we likely don't have a valid real endpoint right now, but we want to ensure it parses the args and invokes the client).

```bash
export API_BASE_URL="http://localhost:8000/v1"
export MODEL_NAME="mock-model"
export HF_TOKEN="mock-token"
python inference.py
```
Expected output: The script should start running, but likely fail connecting or getting valid results from `localhost`.

- [ ] **Step 2: Clean up env vars**
```bash
unset API_BASE_URL MODEL_NAME HF_TOKEN
```
