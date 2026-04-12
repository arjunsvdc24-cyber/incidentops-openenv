#!/usr/bin/env python3
"""
IncidentOps - Inference Baseline Script v15.0

OpenEnv hackathon rules compliance:
- Named inference.py in root directory
- Uses OpenAI client
- Strict stdout format: [START], [STEP] per step, [END]
- Reads API key from environment (Groq default, Gemini, AskSage, OpenAI, HuggingFace)
- Produces reproducible scores on all 3 tasks

Supported providers (set via LLM_PROVIDER env var):
  - groq       (default)  → API_BASE_URL=https://api.groq.com/openai/v1, MODEL_NAME=groq/llama-4-opus-17b
  - gemini                  → API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
  - asksage                 → API_BASE_URL=https://api.asksage.ai/server
  - openai                  → API_BASE_URL=https://api.openai.com/v1
  - huggingface             → API_BASE_URL=https://router.huggingface.co/v1

Usage:
    # Groq (default — no key needed, built-in)
    python inference.py

    # Gemini
    LLM_PROVIDER=gemini GEMINI_API_KEY=your-key python inference.py

    # AskSage
    LLM_PROVIDER=asksage ASKME_API_KEY=your-key python inference.py

    # Specific task
    TASK=oom_crash python inference.py
"""

import asyncio
import os
import sys
import textwrap
from typing import Optional, List

from openai import OpenAI

from app.environment import make_env
from app.fault_injector import FaultType

# =============================================================================
# Configuration
# =============================================================================

PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# Provider defaults
_PROVIDER_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "groq/llama-4-opus-17b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
    "asksage": ("https://api.asksage.ai/server", "gpt-4o"),
    "openai": ("https://api.openai.com/v1", "gpt-4o"),
    "huggingface": ("https://router.huggingface.co/v1", "mistralai/Mistral-7B-Instruct-v0.3"),
}

_PROVIDER_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "asksage": "ASKME_API_KEY",
    "openai": "OPENAI_API_KEY",
    "huggingface": "HF_TOKEN",
}

# HACKATHON: Check injected API_KEY + HF_TOKEN FIRST (before provider-specific keys)
# This ensures the LiteLLM proxy is used when the hackathon injects credentials.
# Sample script pattern: API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
_API_KEY_INJECTED = os.getenv("API_KEY") or os.getenv("HF_TOKEN")

_PROVIDER_KEY = _PROVIDER_KEYS.get(PROVIDER, "GROQ_API_KEY")
_API_KEY_PROVIDER = os.getenv(_PROVIDER_KEY, "")

# Priority: injected hackathon vars > provider-specific env var > Groq built-in
_API_KEY = _API_KEY_INJECTED or _API_KEY_PROVIDER

default_base, default_model = _PROVIDER_DEFAULTS.get(PROVIDER, _PROVIDER_DEFAULTS["groq"])
API_BASE_URL = os.getenv("API_BASE_URL") or default_base
MODEL_NAME = os.getenv("MODEL_NAME") or default_model
API_KEY = _API_KEY

# HACKATHON: Require API_KEY/HF_TOKEN (LiteLLM proxy) OR provider-specific key
if not API_KEY:
    if PROVIDER == "groq":
        sys.stderr.write(f"[ERROR] GROQ_API_KEY or HACKATHON_API_KEY not set. Set API_KEY or GROQ_API_KEY.\n")
    else:
        sys.stderr.write(f"[ERROR] {_PROVIDER_KEYS.get(PROVIDER)} environment variable not set for provider={PROVIDER}.\n")
    sys.exit(1)

MAX_STEPS = int(os.getenv("MAX_STEPS", "50"))
SEED = int(os.getenv("SEED", "42"))
BENCHMARK = "incidentops"

SYSTEM_PROMPT = (
    "You are an on-call SRE diagnosing a production incident across 15 microservices.\n"
    "Available actions: query_service <svc>, query_metrics <svc>, query_logs <svc>,\n"
    "  query_dependencies, query_deployments,\n"
    "  restart_service <svc>, scale_service <svc>, rollback_deployment <svc>,\n"
    "  identify_root_cause <svc>, apply_fix <svc>\n"
    "Rules:\n"
    "  - Always investigate (query) before taking action\n"
    "  - For ghost faults: NO error logs exist. You must check query_metrics for business_metric drift\n"
    "    AND query_deployments for the most recent deploy, then rollback it\n"
    "  - Reply with exactly ONE action as: action_type service\n"
    "    Examples: \"query_metrics payment-service\", \"restart_service payment-service\", \"query_deployments\"\n"
    "  - If the issue is fixed, respond: DONE\n"
)

TASKS = {
    "oom_crash": {"task_id": "oom_crash", "fault_type": "oom", "difficulty": 2},
    "cascade_failure": {"task_id": "cascade_failure", "fault_type": "cascade", "difficulty": 3},
    "ghost_corruption": {"task_id": "ghost_corruption", "fault_type": "ghost", "difficulty": 5},
    "ddos_flood": {"task_id": "ddos_flood", "fault_type": "network", "difficulty": 3},
    "memory_spiral": {"task_id": "memory_spiral", "fault_type": "oom", "difficulty": 4},
}
TASK_TO_RUN = os.getenv("TASK", "")


# =============================================================================
# Logging (strict format per rules)
# =============================================================================

def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    err = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={err}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rstr = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rstr}",
        flush=True,
    )


# =============================================================================
# Action parser
# =============================================================================

ACTION_MAP = {
    "query_service": "query_service",
    "query_metrics": "query_metrics",
    "query_logs": "query_logs",
    "query_dependencies": "query_dependencies",
    "query_deployments": "query_deployments",
    "restart_service": "restart_service",
    "scale_service": "scale_service",
    "rollback_deployment": "rollback_deployment",
    "identify_root_cause": "identify_root_cause",
    "apply_fix": "apply_fix",
    "restart": "restart_service",
    "scale": "scale_service",
    "rollback": "rollback_deployment",
    "identify": "identify_root_cause",
    "fix": "apply_fix",
}


def parse_action(text: str) -> dict:
    text = text.strip().strip('"\'\\').lower()
    if text in ("done", "done()", "done."):
        return {"action_type": "DONE", "target_service": None}
    parts = text.split()
    if not parts:
        return {"action_type": "query_service", "target_service": None}
    at = ACTION_MAP.get(parts[0], parts[0])
    no_target = {"query_dependencies", "query_deployments"}
    return {
        "action_type": at,
        "target_service": parts[1] if len(parts) > 1 and at not in no_target else None,
    }


# =============================================================================
# Prompt builder
# =============================================================================

def build_prompt(obs: dict, step: int) -> str:
    lines = [f"Step {step}. Observation:"]

    info = obs.get("incident_info", {})
    if info:
        lines.append(f"  Fault: {info.get('fault_type')} (difficulty={info.get('difficulty')})")

    svcs = obs.get("services", {})
    unhealthy = [(s, st) for s, st in svcs.items() if st.get("status") != "healthy"]
    if unhealthy:
        lines.append("  Unhealthy services:")
        for s, st in unhealthy[:6]:
            lines.append(
                f"    {s}: {st.get('status')} lat={st.get('latency_ms','?')}ms err={st.get('error_rate',0):.1%}"
            )
    else:
        lines.append("  All appear healthy (ghost: check business_metrics + deployments)")

    for a in obs.get("alerts", [])[:3]:
        lines.append(f"  [{a.get('severity')}] {a.get('service')}: {a.get('message','')[:80]}")

    ar = obs.get("action_result", {})
    if "metrics" in ar:
        m = ar["metrics"]
        lines.append(f"  Metrics: lat={m.get('latency_p50','?')} err={m.get('error_rate','?')} cpu={m.get('cpu_percent','?')}%")
        if "business_metrics" in m:
            for k, v in m["business_metrics"].items():
                lines.append(f"  Biz: {k}={v}")
    if "deployments" in ar:
        for dep in ar["deployments"][-4:]:
            lines.append(f"  Deploy: {dep['service']} {dep['version']} - {dep.get('description','')[:50]}")
    bi = obs.get("business_impact", {})
    if bi:
        lines.append(f"  Revenue: ${bi.get('cumulative_revenue_loss_usd',0):.0f} ({bi.get('severity','normal')})")
    sla = obs.get("sla_deadline", {})
    if sla:
        lines.append(f"  SLA: {sla.get('minutes_remaining')}min ({sla.get('urgency')})")
    if obs.get("fix_applied"):
        lines.append("  FIXED - respond DONE")
    lines.append("Action:")
    return "\n".join(lines)


# =============================================================================
# Run one task
# =============================================================================

async def run_task(client: OpenAI, task_def: dict, seed: int = SEED) -> dict:
    tid = task_def["task_id"]
    ft = task_def["fault_type"]
    df = task_def["difficulty"]

    log_start(tid, MODEL_NAME)

    env = make_env(
        seed=seed,
        fault_type=FaultType(ft),
        difficulty=df,
        max_steps=MAX_STEPS,
        enable_noise=True,
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    rewards: List[float] = []
    steps_taken = 0
    done = False
    score = 0.0

    try:
        obs = dict(env.reset(seed=seed))
        messages.append({"role": "user", "content": build_prompt(obs, 0)})

        for step_num in range(1, MAX_STEPS + 1):
            # Get LLM action
            try:
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=80,
                )
                llm_text = (completion.choices[0].message.content or "").strip()
                messages.append({"role": "assistant", "content": llm_text})
            except Exception as e:
                log_step(step_num, "ERROR", 0.0, True, str(e)[:100])
                break

            # Parse and validate
            action_dict = parse_action(llm_text)

            if action_dict["action_type"] == "DONE" or env.fix_applied:
                log_step(step_num, "DONE", 0.0, True, None)
                done = True
                break

            # Execute
            step_error = None
            try:
                result = env.step(action_dict)
            except Exception as e:
                log_step(step_num, llm_text[:80], 0.0, False, str(e)[:100])
                obs = {}
                reward = 0.0
                done = False
            else:
                obs = dict(result.observation) if hasattr(result.observation, "__dict__") else result.observation
                reward = float(result.reward)
                done = bool(result.terminated or result.truncated)
                # Capture error from action_result
                step_error = obs.get("action_result", {}).get("error")

            rewards.append(reward)
            steps_taken = step_num

            action_str = action_dict["action_type"]
            if action_dict.get("target_service"):
                action_str += f" {action_dict['target_service']}"

            log_step(step_num, action_str[:80], reward, done, step_error)

            if done:
                break

            messages.append({"role": "user", "content": build_prompt(obs, step_num)})

        # Normalize score to strictly (0, 1) — validator requires scores > 0.0 and < 1.0
        # Validator uses round(x, 3), so eps must be >= 0.001:
        #   round(1.0 - 0.001, 3) = 0.999 < 1.0, round(0.001, 3) = 0.001 > 0.0
        _EPSILON = 0.001
        score = min(max(sum(rewards) / 10.0, _EPSILON), 1.0 - _EPSILON)

    finally:
        try:
            env.close()
        except Exception:
            pass
        log_end(score >= 0.3, steps_taken, score, rewards)

    return {"task_id": tid, "steps": steps_taken, "score": score, "success": score >= 0.3}


# =============================================================================
# Main
# =============================================================================

async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    tasks_to_run = (
        [TASKS[TASK_TO_RUN]] if TASK_TO_RUN and TASK_TO_RUN in TASKS else list(TASKS.values())
    )

    for task_def in tasks_to_run:
        try:
            await run_task(client, task_def)
        except Exception as e:
            sys.stderr.write(f"[ERROR] {task_def['task_id']}: {e}\n")
            log_start(task_def["task_id"], MODEL_NAME)
            log_end(False, 0, 0.0, [])


if __name__ == "__main__":
    asyncio.run(main())
