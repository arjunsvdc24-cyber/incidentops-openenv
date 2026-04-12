from typing import Any
"""
IncidentOps - LLM Baseline Agent v13.0

Uses OpenAI API for intelligent incident response.

Requirements:
- OPENAI_API_KEY environment variable
- openai package

Features:
- Sends observation to LLM
- Gets structured action JSON
- Reproducible with seed

Runs evaluation for easy, medium, hard difficulties.
"""
from dataclasses import dataclass, field
import os
import json
import random

# OpenAI import with fallback
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:  # pragma: no cover
    HAS_OPENAI = False  # pragma: no cover
    OpenAI = None  # pragma: no cover


@dataclass
class LLMAgentConfig:
    """Configuration for LLM agent"""
    seed: int = 42
    model: str = os.environ.get("MODEL_NAME", "groq/llama-4-opus-17b")
    max_tokens: int = 500
    temperature: float = 0.0  # Deterministic
    max_steps: int = 20


@dataclass
class EvaluationResult:
    """Result of evaluation run"""
    difficulty: str
    score: float
    steps: int
    success: bool
    actions: list[dict]


SYSTEM_PROMPT = """You are an expert SRE (Site Reliability Engineer) agent responding to production incidents.

Your role is to:
1. Investigate the incident systematically
2. Identify the root cause service
3. Apply the correct fix to minimize MTTR

## FAULT TYPE DIAGNOSIS

CRITICAL: The fault_type tells you what pattern to look for:

- **OOM/Crash**: High memory/CPU on a service → restart_service on that service
- **Cascade**: Queue buildup + slow responses → scale_service on bottleneck
- **Ghost** (HARD): ALL metrics look healthy, but business metrics (CTR, quality) are degraded. No error logs. → This means a silent logic/data bug from a RECENT DEPLOYMENT. FIRST ACTION: query_deployments. Find the service with the suspicious deployment (keywords: refactor, algorithm, optimize, v2), then rollback_deployment.
- **Network**: Services unreachable or returning 503 → reroute_traffic

## GHOST SCENARIO RULE
If you see NO alerts and NO unhealthy services, but the incident_info says fault_type=ghost:
→ Check query_deployments FIRST
→ Look for recent deploys with suspicious descriptions
→ Rollback the suspicious deployment

## Available actions:
- query_service: Get service status (target: service name)
- query_metrics: Get service metrics including business metrics (target: service name)
- query_logs: Get service logs (target: service name)
- query_dependencies: Get service dependency graph
- query_deployments: Get deployment timeline (CRITICAL for ghost)
- query_memory: Query incident memory
- restart_service: Restart a service (for crashes/OOM)
- scale_service: Scale a service (for cascade/queue buildup)
- rollback_deployment: Rollback a bad deployment (for ghost)
- reroute_traffic: Reroute traffic (for network issues)
- identify_root_cause: Declare root cause (target: service name)

Valid services: api-gateway, user-service, auth-service, payment-service, order-service,
inventory-service, recommendation-service, notification-service, cache-service,
database-primary, database-replica, search-service, analytics-service, email-service, shipping-service

Respond with ONLY a JSON object:
{
  "action_type": "action_name",
  "target_service": "service_name or null",
  "reasoning": "brief explanation"
}

Strategy: If no errors appear but business metrics are bad → query_deployments first."""


class LLMBaselineAgent:
    """
    LLM-powered baseline agent for incident response.
    
    Uses OpenAI API for intelligent decision making.
    Deterministic with temperature=0 and seed.
    """
    
    def __init__(
        self,
        config: LLMAgentConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.config = config or LLMAgentConfig()
        self.rng = random.Random(self.config.seed)

        # Initialize OpenAI client — HACKATHON PRIORITY: use injected API_BASE_URL + API_KEY first
        # These are set by the hackathon evaluation infrastructure
        _hackathon_key = os.environ.get("API_KEY")
        _hackathon_url = os.environ.get("API_BASE_URL")
        if _hackathon_key and _hackathon_url:
            self.api_key = _hackathon_key
            self.base_url = _hackathon_url
        else:
            # Fall back to explicitly passed values, then provider-specific env vars
            self.api_key = (
                api_key
                or os.environ.get("GROQ_API_KEY")
                or os.environ.get("HF_TOKEN")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("ASKME_API_KEY")
                or ""
            )
            self.base_url = base_url or os.environ.get(
                "API_BASE_URL", "https://api.groq.com/openai/v1"
            )
        self.provider = os.environ.get("LLM_PROVIDER", "openai")
        if model:
            self.config.model = model

        if HAS_OPENAI and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self.client = None
        else:
            self.client = None

        # State tracking
        self.action_history: list[dict] = []
        self.current_step = 0
    
    def reset(self, seed: int | None = None) -> None:
        """Reset agent for new episode"""
        if seed is not None:
            self.config.seed = seed
            self.rng = random.Random(seed)
        
        self.action_history = []
        self.current_step = 0
    
    def act(self, observation: dict) -> dict:
        """
        Choose action based on observation using LLM.
        
        Args:
            observation: Current environment observation
            
        Returns:
            Action dict for environment
        """
        self.current_step = observation.get("step", self.current_step)
        
        if self.client:
            action = self._get_llm_action(observation)
        else:
            action = self._get_fallback_action(observation)
        
        # Record action
        self.action_history.append(action)
        
        return action
    
    def _get_llm_action(self, observation: dict) -> dict:
        """Get action from LLM with robust JSON parsing"""
        for attempt in range(3):
            try:
                obs_str = self._format_observation(observation)

                response = self.client.chat.completions.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    seed=self.config.seed,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Current observation:\n{obs_str}\n\nWhat action should I take next? Respond with JSON only."},
                    ]
                )

                content = response.choices[0].message.content.strip()

                # Parse JSON — handle markdown code blocks
                for marker in ["```json", "```"]:
                    if marker in content:
                        parts = content.split(marker)
                        if len(parts) > 1:
                            content = parts[1].split("```")[0].strip()
                            break

                # Try to find JSON object in partial responses
                if not content.startswith("{"):
                    idx = content.find("{")
                    if idx >= 0:
                        content = content[idx:]

                action = json.loads(content)

                return {
                    "action_type": action.get("action_type", "query_service"),
                    "target_service": action.get("target_service"),
                    "parameters": {},
                }

            except Exception:
                if attempt == 2:
                    return self._get_fallback_action(observation)

        return self._get_fallback_action(observation)
    
    def _get_fallback_action(self, observation: dict) -> dict:
        """Fallback action when LLM unavailable — ghost-aware rule-based agent"""
        alerts = observation.get("alerts", [])
        services = observation.get("services", {})
        incident = observation.get("incident_info", {})
        fault_type = incident.get("fault_type", "oom")
        action_types = [a.get("action_type") for a in self.action_history]

        # Find problematic services
        problem_services = [
            svc for svc, state in services.items()
            if state.get("status") in ("degraded", "unhealthy")
        ]

        # Ghost scenario: no alerts, no unhealthy services, but business metrics bad
        is_ghost = fault_type == "ghost" and not alerts and not problem_services

        if is_ghost:
            # Ghost: go straight to deployment timeline
            if "query_deployments" not in action_types:
                return {"action_type": "query_deployments", "target_service": None, "parameters": {}}
            if "query_dependencies" not in action_types:
                return {"action_type": "query_dependencies", "target_service": None, "parameters": {}}
            # After investigating, rollback the first suspicious deployment service
            # Look for recommendation/analytics/search services as common ghost candidates
            for svc in ["recommendation-service", "analytics-service", "search-service"]:
                if svc in services and "rollback_deployment" not in action_types:
                    return {"action_type": "rollback_deployment", "target_service": svc, "parameters": {}}
            return {"action_type": "query_deployments", "target_service": None, "parameters": {}}

        if alerts:
            target = alerts[0].get("service")
            if target:
                return {"action_type": "query_logs", "target_service": target, "parameters": {}}

        if problem_services:
            target = problem_services[0]
            queried_logs = any(
                a.get("target_service") == target and a.get("action_type") == "query_logs"
                for a in self.action_history
            )
            queried_metrics = any(
                a.get("target_service") == target and a.get("action_type") == "query_metrics"
                for a in self.action_history
            )
            if not queried_logs:
                return {"action_type": "query_logs", "target_service": target, "parameters": {}}
            elif not queried_metrics:
                return {"action_type": "query_metrics", "target_service": target, "parameters": {}}
            elif fault_type == "cascade":
                return {"action_type": "scale_service", "target_service": target, "parameters": {}}
            elif fault_type == "network":
                return {"action_type": "reroute_traffic", "target_service": target, "parameters": {}}
            else:
                return {"action_type": "restart_service", "target_service": target, "parameters": {}}

        # No signals — query deployments
        if "query_deployments" not in action_types:
            return {"action_type": "query_deployments", "target_service": None, "parameters": {}}
        all_services = list(services.keys())
        if all_services:
            return {"action_type": "query_service", "target_service": self.rng.choice(all_services), "parameters": {}}
        return {"action_type": "query_deployments", "target_service": None, "parameters": {}}
    
    def _format_observation(self, observation: dict) -> str:
        """Format observation for LLM prompt"""
        parts = []
        
        # Step info
        parts.append(f"Step: {observation.get('step', 0)}")
        
        # Alerts
        alerts = observation.get("alerts", [])
        if alerts:
            parts.append("\nAlerts:")
            for alert in alerts[:5]:
                parts.append(f"  - [{alert.get('severity', 'info').upper()}] {alert.get('service')}: {alert.get('message')}")
        
        # Service states
        services = observation.get("services", {})
        problem_services = {
            k: v for k, v in services.items()
            if v.get("status") in ("degraded", "unhealthy")
        }
        if problem_services:
            parts.append("\nProblem Services:")
            for svc, state in problem_services.items():
                parts.append(f"  - {svc}: {state.get('status')} (latency: {state.get('latency_ms', 0):.0f}ms, error: {state.get('error_rate', 0):.1%})")
        
        # Incident info
        incident = observation.get("incident_info", {})
        if incident:
            parts.append(f"\nIncident Type: {incident.get('fault_type', 'unknown')}")
            parts.append(f"Difficulty: {incident.get('difficulty', 3)}")
        
        # Recent actions
        if self.action_history:
            parts.append("\nRecent Actions:")
            for action in self.action_history[-3:]:
                parts.append(f"  - {action.get('action_type')} -> {action.get('target_service')}")
        
        return "\n".join(parts)


def run_llm_evaluation(
    seed: int = 42,
    max_steps: int = 20,
    verbose: bool = False,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Run LLM agent evaluation across difficulties.

    Args:
        seed: Random seed
        max_steps: Maximum steps per episode
        verbose: Print progress
        api_key: OpenAI/Groq API key (passed directly, not via env)
        base_url: API base URL (passed directly, not via env)
        model: Model name (passed directly, not via env)

    Returns:
        Dict with easy, medium, hard, total scores
    """
    from app.environment import make_env
    from app.enhanced_grader import EnhancedSREGrader
    from app.fault_injector import FaultType

    results = {}

    difficulties = [
        ("easy", 2, FaultType.OOM),
        ("medium", 3, FaultType.CASCADE),
        ("hard", 5, FaultType.GHOST),
    ]

    for name, difficulty, fault in difficulties:
        if verbose:
            print(f"\n{'='*50}")
            print(f"Running {name} evaluation (difficulty={difficulty})")
            print(f"{'='*50}")

        # Create environment
        env = make_env(seed=seed, difficulty=difficulty, fault_type=fault)
        obs = env.reset(seed=seed)

        # Create agent with explicit credentials (no env vars needed)
        config = LLMAgentConfig(seed=seed, max_steps=max_steps)
        agent = LLMBaselineAgent(config, api_key=api_key, base_url=base_url, model=model)
        agent.reset(seed=seed)
        
        total_reward = 0.0
        steps = 0
        
        for step in range(max_steps):
            # Get action
            action = agent.act(obs)
            
            if verbose:
                print(f"Step {step}: {action.get('action_type')} -> {action.get('target_service')}")
            
            # Execute action
            response = env.step(action)
            total_reward += response.reward
            steps = step + 1
            
            obs = response.observation
            
            if response.terminated or response.truncated:
                if verbose:
                    print(f"Episode ended: {'terminated' if response.terminated else 'truncated'}")
                break
        
        # Grade trajectory
        grader = EnhancedSREGrader(seed=seed)
        
        trajectory = {
            "actions": agent.action_history,
            "final_state": {"fix_applied": response.terminated if 'response' in dir() else False},
        }
        
        scenario = {
            "fault_type": env.current_scenario.fault_type.value if env.current_scenario else "unknown",
            "root_cause_service": env.current_scenario.root_cause_service if env.current_scenario else "",
            "affected_services": env.current_scenario.affected_services if env.current_scenario else [],
        }
        
        eval_result = grader.grade(trajectory, scenario)
        
        results[name] = {
            "score": round(eval_result.breakdown.final_score, 9),  # 9dp preserves eps=0.001 bounds
            "steps": steps,
            "total_reward": round(total_reward, 3),
            "grade": eval_result.breakdown.grade.value,
        }
        
        if verbose:
            print(f"\n{name.capitalize()} Result:")
            print(f"  Score: {results[name]['score']}")
            print(f"  Grade: {results[name]['grade']}")
            print(f"  Steps: {results[name]['steps']}")
    
    # Calculate total
    total_score = sum(r["score"] for r in results.values()) / len(results)
    results["total"] = round(total_score, 3)
    
    if verbose:
        print(f"\n{'='*50}")
        print(f"OVERALL: {results['total']}")
        print(f"{'='*50}")
    
    return {
        "easy": results["easy"]["score"],
        "medium": results["medium"]["score"],
        "hard": results["hard"]["score"],
        "total": results["total"],
    }


def check_openai_available(api_key: str | None = None) -> bool:
    """Check if LLM API is available"""
    # HACKATHON: Check injected env vars first
    if os.environ.get("API_KEY") and os.environ.get("API_BASE_URL"):
        return HAS_OPENAI
    if api_key:
        return HAS_OPENAI
    return HAS_OPENAI and (
        os.environ.get("GROQ_API_KEY") is not None
        or os.environ.get("HF_TOKEN") is not None
        or os.environ.get("OPENAI_API_KEY") is not None
        or os.environ.get("GEMINI_API_KEY") is not None
        or os.environ.get("ASKME_API_KEY") is not None
    )


# Compatibility with existing baseline module
def run_baseline_episode(
    env,
    agent=None,
    seed=42,
    max_steps=20,
    verbose=True,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
):
    """Run baseline episode (compatibility wrapper)"""
    config = LLMAgentConfig(seed=seed, max_steps=max_steps)
    llm_agent = LLMBaselineAgent(config, api_key=api_key, base_url=base_url, model=model)
    llm_agent.reset(seed=seed)
    
    obs = env.reset(seed=seed)
    total_reward = 0.0
    steps = 0
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"LLM BASELINE AGENT EPISODE (seed={seed})")
        print(f"{'='*60}\n")
    
    for step in range(max_steps):
        action = llm_agent.act(obs)
        
        if verbose:
            print(f"Step {step}: {action.get('action_type')} -> {action.get('target_service')}")
        
        response = env.step(action)
        total_reward += response.reward
        steps = step + 1
        obs = response.observation
        
        if response.terminated or response.truncated:
            if verbose:
                print(f"\nEpisode ended: {'terminated' if response.terminated else 'truncated'}")
            break
    
    from app.enhanced_grader import EnhancedSREGrader
    grader = EnhancedSREGrader(seed=seed)
    
    trajectory = {
        "actions": llm_agent.action_history,
        "final_state": {"fix_applied": response.terminated},
    }
    
    scenario = {
        "fault_type": env.current_scenario.fault_type.value if env.current_scenario else "unknown",
        "root_cause_service": env.current_scenario.root_cause_service if env.current_scenario else "",
        "affected_services": env.current_scenario.affected_services if env.current_scenario else [],
    }
    
    eval_result = grader.grade(trajectory, scenario)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Score: {eval_result.breakdown.final_score:.3f}")
        print(f"Grade: {eval_result.breakdown.grade.value}")
        print(f"{'='*60}\n")
    
    return {
        "steps": steps,
        "total_reward": total_reward,
        "final_score": eval_result.breakdown.final_score,
        "grade": eval_result.breakdown.grade.value,
    }
