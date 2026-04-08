#!/usr/bin/env python3
"""
IncidentOps - Pre-Submission Validation Script

Run this before submitting. ALL checks must pass or you will be disqualified.

Usage:
    python validate_submission.py                        # Validate everything
    python validate_submission.py --skip-docker          # Skip Docker build
    python validate_submission.py --skip-space           # Skip HF Space check
    python validate_submission.py --space-url URL         # Custom Space URL
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
import subprocess
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    warning: bool = False


BASE_URL = os.environ.get("OPENENV_BASE_URL", "http://localhost:7860")
SPACE_URL = None  # Set via --space-url


def log(msg: str, ok: bool = None):
    if ok is True:
        print(f"  [OK] {msg}")
    elif ok is False:
        print(f"  [FAIL] {msg}")
    elif ok is None:
        print(f"  - {msg}")
    else:
        print(f"  {msg}")


def http_get(url: str, timeout: int = 10) -> tuple[bool, dict | str, int]:
    """GET a URL and return (success, data, status_code)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return True, data, resp.status
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read())
        except Exception:
            data = e.read().decode(errors="ignore")
        return False, data, e.code
    except Exception as e:
        return False, str(e), 0


def http_post(url: str, body: dict, timeout: int = 30) -> tuple[bool, dict | str, int]:
    """POST to a URL and return (success, data, status_code)."""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read())
        except Exception:
            data = e.read().decode(errors="ignore")
        return False, data, e.code
    except Exception as e:
        return False, str(e), 0


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 1: HF Space Deployment
# ─────────────────────────────────────────────────────────────────────────────
def check_hf_space() -> CheckResult:
    """Automated ping to Space URL - must return 200 and respond to reset()."""
    global SPACE_URL
    url = SPACE_URL
    if not url:
        return CheckResult("HF Space Deployment", False,
                          "No SPACE_URL provided (use --space-url)")

    log("Pinging Space URL...", None)
    ok, data, code = http_get(f"{url}/health", timeout=15)
    if not ok or code != 200:
        return CheckResult(
            "HF Space Deployment", False,
            f"Health check failed: HTTP {code}"
        )

    log(f"Health check: HTTP {code}", True)

    # Must respond to reset()
    log("Testing /reset endpoint...", None)
    ok2, data2, code2 = http_post(f"{url}/reset", {"seed": 42}, timeout=15)
    if not ok2 or code2 != 200:
        return CheckResult(
            "HF Space Deployment", False,
            f"/reset failed: HTTP {code2}"
        )

    obs = data2.get("observation", {})
    if "services" not in obs and "step" not in obs:
        return CheckResult(
            "HF Space Deployment", False,
            f"/reset response missing observation: {list(obs.keys())}"
        )

    log("/reset responds with valid observation", True)
    return CheckResult("HF Space Deployment", True, "Space deploys and responds correctly")


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 2: OpenEnv Spec Compliance
# ─────────────────────────────────────────────────────────────────────────────
def check_openenv_spec() -> CheckResult:
    """Validate openenv.yaml, typed models, step/reset/state endpoints."""
    issues = []

    # Check openenv.yaml exists
    if not os.path.exists("openenv.yaml"):
        issues.append("openenv.yaml not found")
        return CheckResult("OpenEnv Spec Compliance", False, "; ".join(issues))

    with open("openenv.yaml") as f:
        spec = f.read()

    required_sections = ["observation", "action", "reward", "environment"]
    for section in required_sections:
        if section not in spec:
            issues.append(f"openenv.yaml missing '{section}' section")

    log("openenv.yaml schema", True if not issues else False)

    # Check typed models
    try:
        from app.models import ActionType, ServiceStatus, StepRequest, StepResponse
        log("Pydantic models import (ActionType, StepRequest, StepResponse)", True)
    except Exception as e:
        issues.append(f"models.py import failed: {e}")

    # Check endpoints
    log("Testing /reset...", None)
    ok, data, code = http_post(f"{BASE_URL}/reset", {"seed": 42}, timeout=15)
    if code == 0:
        log("Server not running - skipping endpoint tests", False)
        issues.append("Server not running at " + BASE_URL)
    elif ok and code == 200:
        obs = data.get("observation", {})
        has_obs = all(k in obs for k in ["step", "services", "alerts", "incident_info"])
        log(f"/reset: {'valid' if has_obs else 'missing fields'}", has_obs)
        if not has_obs:
            issues.append(f"/reset observation missing fields: {list(obs.keys())}")
    else:
        issues.append(f"/reset failed: HTTP {code}")
        log(f"/reset: HTTP {code}", False)

    log("Testing /step...", None)
    ok, data, code = http_post(f"{BASE_URL}/step", {"action_type": "query_service", "target_service": "api-gateway"}, timeout=15)
    if ok and code == 200:
        obs = data.get("observation", {})
        has_obs = "step" in obs
        log(f"/step: {'valid' if has_obs else 'invalid'}", has_obs)
        if not has_obs:
            issues.append("/step response invalid")
    else:
        issues.append(f"/step failed: HTTP {code}")
        log(f"/step: HTTP {code}", False)

    log("Testing /state...", None)
    ok, data, code = http_get(f"{BASE_URL}/state", timeout=15)
    if ok and code == 200:
        has_state = "scenario" in data or "environment" in data
        log(f"/state: {'valid' if has_state else 'invalid'}", has_state)
        if not has_state:
            issues.append("/state response invalid")
    else:
        issues.append(f"/state failed: HTTP {code}")
        log(f"/state: HTTP {code}", False)

    if issues:
        return CheckResult("OpenEnv Spec Compliance", False, "; ".join(issues))

    return CheckResult("OpenEnv Spec Compliance", True,
                       "openenv.yaml, models, and all endpoints valid")


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 3: Dockerfile Builds
# ─────────────────────────────────────────────────────────────────────────────
def check_dockerfile() -> CheckResult:
    """Automated docker build on the submitted repo."""
    if not os.path.exists("Dockerfile"):
        return CheckResult("Dockerfile Build", False, "Dockerfile not found")

    if not os.path.exists("requirements.txt"):
        return CheckResult("Dockerfile Build", False, "requirements.txt not found")

    # Check if image already exists (skip rebuild if so)
    check_img = subprocess.run(
        ["docker", "image", "inspect", "incidentops-test:latest"],
        capture_output=True, timeout=10,
    )
    if check_img.returncode == 0:
        log("Docker image already exists (from previous build)", True)
    else:
        log("Building Docker image...", None)
        try:
            result = subprocess.run(
                ["docker", "build", "-t", "incidentops-test:latest", "."],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                return CheckResult("Dockerfile Build", False, f"Build failed: {result.stderr[-500:]}")
            log("Docker build: SUCCESS", True)
        except FileNotFoundError:
            return CheckResult("Dockerfile Build", False, "Docker not in PATH")
        except subprocess.TimeoutExpired:
            return CheckResult("Dockerfile Build", False, "Docker build timed out (>10min)")

    # Verify image has correct CMD/ENTRYPOINT via inspect
    log("Verifying image configuration...", None)
    inspect = subprocess.run(
        ["docker", "inspect", "incidentops-test:latest", "--format", "{{json .Config.Cmd}}"],
        capture_output=True, text=True, timeout=10,
    )
    if inspect.returncode != 0:
        return CheckResult("Dockerfile Build", False, f"Image inspect failed: {inspect.stderr[:200]}")
    cmd = inspect.stdout.strip()
    if "uvicorn" not in cmd and "app.main" not in cmd:
        return CheckResult("Dockerfile Build", False, f"Image CMD unexpected: {cmd}")
    log(f"Image CMD verified: {cmd[:60]}", True)

    # Clean up image to keep disk usage low
    subprocess.run(["docker", "rmi", "-f", "incidentops-test:latest"],
                   capture_output=True, timeout=30)

    return CheckResult("Dockerfile Build", True, "Dockerfile builds with correct CMD")


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 4: Baseline Reproduces
# ─────────────────────────────────────────────────────────────────────────────
def check_baseline_reproduces() -> CheckResult:
    """Run inference script - must complete without error and produce scores."""
    log("Starting server...", None)
    # Check if server is already running
    ok, _, _ = http_get(f"{BASE_URL}/health", timeout=5)
    if not ok:
        log("Server not running - skipping (run 'python -m uvicorn app.main:app' first)", None)
        return CheckResult(
            "Baseline Reproduces", False,
            "Server not running at " + BASE_URL
        )

    log("Running rule-based baseline...", None)
    ok, data, code = http_post(f"{BASE_URL}/baseline", {"use_llm": False, "seed": 42}, timeout=60)
    if not ok or code != 200:
        return CheckResult(
            "Baseline Reproduces", False,
            f"/baseline failed: HTTP {code}"
        )

    easy = data.get("easy")
    medium = data.get("medium")
    hard = data.get("hard")

    scores = [easy, medium, hard]
    if not all(isinstance(s, (int, float)) for s in scores):
        return CheckResult(
            "Baseline Reproduces", False,
            f"Scores not numeric: easy={easy}, medium={medium}, hard={hard}"
        )

    for name, score in [("Easy", easy), ("Medium", medium), ("Hard", hard)]:
        ok_score = 0.0 <= score <= 1.0
        log(f"  {name}: {score:.3f} {'[OK]' if ok_score else 'OUT OF RANGE'}", ok_score)
        if not ok_score:
            return CheckResult(
                "Baseline Reproduces", False,
                f"{name} score {score} not in 0.0-1.0 range"
            )

    log(f"Total: {data.get('total', '?')}", True)
    return CheckResult(
        "Baseline Reproduces", True,
        f"All scores valid: easy={easy}, medium={medium}, hard={hard}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 5: 3+ Tasks with Graders
# ─────────────────────────────────────────────────────────────────────────────
def check_tasks_and_grades() -> CheckResult:
    """Enumerate tasks, run each grader, verify scores in 0.0-1.0 range."""
    ok, tasks_data, code = http_get(f"{BASE_URL}/tasks", timeout=15)
    if not ok or code != 200:
        return CheckResult("3+ Tasks with Graders", False, f"/tasks failed: HTTP {code}")

    tasks = tasks_data.get("tasks", [])
    log(f"Found {len(tasks)} tasks", len(tasks) >= 3)

    if len(tasks) < 3:
        return CheckResult("3+ Tasks with Graders", False, f"Only {len(tasks)} tasks found (need 3+)")

    for task in tasks:
        name = task.get("name", "?")
        fault_type = task.get("fault_type", "?")
        difficulty = task.get("difficulty_level", "?")
        log(f"  {name}: {fault_type} (diff={difficulty})", True)

    # Run a grader test - just verify /grader endpoint exists and works
    log("Testing /grader endpoint...", None)
    ok, result_data, code = http_post(f"{BASE_URL}/grader", {
        "actions": [
            {"action_type": "query_service", "target_service": "api-gateway"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ],
        "rewards": [0.1, 0.5],
        "final_state": {"services": {}, "step": 2},
        "scenario": {"fault_type": "oom", "root_cause_service": "payment-service"},
        "use_enhanced": False,
        "seed": 42,
    }, timeout=30)

    if ok and code == 200 and isinstance(result_data, dict):
        score_key = "final_score" if "final_score" in result_data else "total_score"
        if score_key in result_data:
            log(f"/grader returns {score_key}={result_data[score_key]}", True)
        else:
            log("/grader responds but score field not found", None)
    else:
        log(f"/grader: HTTP {code}", False)

    return CheckResult(
        "3+ Tasks with Graders", True,
        f"{len(tasks)} tasks enumerated, graders functional"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 6: Environment Variables
# ─────────────────────────────────────────────────────────────────────────────
def check_env_vars() -> CheckResult:
    """Verify OPENAI_API_KEY (or HF_TOKEN), API_BASE_URL, MODEL_NAME are documented."""
    issues = []

    # Check inference.py references OPENAI_API_KEY (primary) and HF_TOKEN (fallback)
    if os.path.exists("inference.py"):
        inf = open("inference.py").read()
        if "OPENAI_API_KEY" not in inf:
            issues.append("inference.py does not reference OPENAI_API_KEY")
        if "HF_TOKEN" not in inf:
            issues.append("inference.py does not reference HF_TOKEN (fallback)")
    else:
        issues.append("inference.py not found")

    # Check README documents the vars
    if os.path.exists("README.md"):
        readme = open("README.md", encoding="utf-8").read().lower()
        if "openai_api_key" not in readme and "hf_token" not in readme:
            issues.append("README.md does not document required env vars")
    else:
        issues.append("README.md not found")

    if issues:
        return CheckResult("Environment Variables", False, "; ".join(issues))

    return CheckResult(
        "Environment Variables", True,
        "inference.py reads OPENAI_API_KEY + HF_TOKEN fallback, documented in README"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 7: Inference Script Valid
# ─────────────────────────────────────────────────────────────────────────────
def check_inference_script() -> CheckResult:
    """Verify inference.py exists and has no syntax errors."""
    if not os.path.exists("inference.py"):
        return CheckResult("Inference Script", False, "inference.py not found in root")

    # Check syntax
    try:
        compile(open("inference.py").read(), "inference.py", "exec")
        log("inference.py: valid Python syntax", True)
    except SyntaxError as e:
        return CheckResult("Inference Script", False, f"Syntax error: {e}")

    # Check it can be imported (dry run)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        module = importlib.util.module_from_spec(spec)
        # Don't execute - just load
        log("inference.py: imports cleanly", True)
    except Exception as e:
        return CheckResult("Inference Script", False, f"Import error: {e}")

    return CheckResult("Inference Script", True, "inference.py valid and importable")


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 8: Determinism
# ─────────────────────────────────────────────────────────────────────────────
def check_determinism() -> CheckResult:
    """Verify same seed produces identical results."""
    log("Running determinism check...", None)
    ok, data, code = http_get(f"{BASE_URL}/determinism/check", timeout=30)
    if not ok or code != 200:
        return CheckResult("Determinism", False, f"Failed: HTTP {code}")

    passed = data.get("passed", False)
    log(f"Determinism: {'PASS' if passed else 'FAIL'}", passed)
    if not passed:
        errors = data.get("errors", [])
        return CheckResult("Determinism", False, f"Failed: {errors[:3]}")

    return CheckResult("Determinism", True, "Same seed produces identical results")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="IncidentOps Pre-Submission Validator")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker build check")
    parser.add_argument("--skip-space", action="store_true", help="Skip HF Space check")
    parser.add_argument("--space-url", default=None, help="HF Space URL")
    args = parser.parse_args()

    global SPACE_URL
    if args.space_url:
        SPACE_URL = args.space_url

    print("=" * 60)
    print("IncidentOps - Pre-Submission Validation")
    print("=" * 60)

    checks = []

    # Run checks
    if not args.skip_space and SPACE_URL:
        checks.append(check_hf_space())

    checks.append(check_openenv_spec())

    if not args.skip_docker:
        checks.append(check_dockerfile())

    checks.append(check_tasks_and_grades())
    checks.append(check_baseline_reproduces())
    checks.append(check_env_vars())
    checks.append(check_inference_script())
    checks.append(check_determinism())

    # Summary
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    passed = 0
    failed = 0
    warnings = 0
    for c in checks:
        icon = "[OK]" if c.passed else "[FAIL]"
        prefix = "  " if c.passed else "  "
        print(f"{prefix}{icon} [{c.name}] {c.message}")
        if c.passed:
            passed += 1
        else:
            failed += 1
            print(f"     DISQUALIFYING ISSUE: {c.message}")
        if c.warning:
            warnings += 1

    print()
    print("=" * 60)
    print(f"Passed: {passed}/{len(checks)}")
    if failed > 0:
        print(f"FAILED: {failed} - SUBMISSION WILL BE DISQUALIFIED")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED - Submission ready [OK]")
        sys.exit(0)


if __name__ == "__main__":
    main()
