"""
IncidentOps - Agent Coordinator

Orchestrates multiple agents working on the same incident:
- Investigator: gathers evidence
- Fixer: applies fixes (activates when suspicion > threshold)
- Analyst: provides pattern-based hints
"""
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from app.agents.base import BaseAgent, AgentObservation, AgentDecision
from app.agents.investigator import InvestigatorAgent
from app.agents.fixer import FixerAgent
from app.agents.analyst import AnalystAgent

if TYPE_CHECKING:
    from app.environment import IncidentEnv


@dataclass
class MultiAgentEpisodeResult:
    """Result from a multi-agent episode"""
    total_reward: float
    final_score: float
    grade: str
    steps: int
    agent_decisions: Dict[str, List[AgentDecision]]
    episode_id: str
    duration_ms: int
    investigation_summary: Dict[str, Any] = field(default_factory=dict)
    fix_summary: Dict[str, Any] = field(default_factory=dict)
    analysis_summary: Dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    """
    Coordinates multiple agents working on the same incident.

    Roles:
    - Investigator: gathers evidence
    - Fixer: applies fixes (activates when suspicion > threshold)
    - Analyst: provides pattern-based hints

    Communication:
    - Agents share a common observation state
    - Analyst's hints are broadcast to all agents
    - Fixer activates only when Investigator reaches confidence threshold
    """

    def __init__(
        self,
        enable_analyst: bool = True,
        confidence_threshold: float = 0.7,
        max_steps: int = 20,
    ):
        """
        Initialize the coordinator.

        Args:
            enable_analyst: Whether to enable the Analyst agent
            confidence_threshold: Suspicion threshold for Fixer activation
            max_steps: Maximum steps per episode
        """
        self.investigator = InvestigatorAgent()
        self.fixer = FixerAgent()
        self.analyst = AnalystAgent() if enable_analyst else None
        self.confidence_threshold = confidence_threshold
        self.max_steps = max_steps
        self.enable_analyst = enable_analyst

    def run_episode(
        self,
        env: "IncidentEnv",
        seed: int = 42,
    ) -> MultiAgentEpisodeResult:
        """
        Run a full episode with coordinated agents.

        Loop:
        1. Get observation from env
        2. Analyst provides hints based on observation
        3. Investigator decides action
        4. If suspicion > threshold, Fixer takes over
        5. Execute action in env
        6. Record decision, update agent states
        7. Repeat until terminated or max_steps
        """
        start_time = time.time()

        # Reset environment and all agents
        env.reset(seed=seed)
        self.investigator.reset(seed)
        self.fixer.reset(seed)
        if self.analyst:
            self.analyst.reset(seed)

        # Generate deterministic episode ID
        episode_id = hashlib.md5(
            f"{seed}{start_time}".encode()
        ).hexdigest()[:16]

        # Track all decisions per agent
        all_decisions: Dict[str, List[AgentDecision]] = {
            "investigator": [],
            "fixer": [],
            "analyst": [],
        }

        total_reward = 0.0
        observations = []
        analyst_hint: Optional[str] = None

        for step in range(self.max_steps):
            # Build AgentObservation
            agent_obs = AgentObservation(
                step=env.current_step,
                action_history=[
                    {"action_type": d.action_type, "target_service": d.target_service}
                    for d in all_decisions["investigator"] + all_decisions["fixer"]
                ],
                reward_history=list(env.episode_rewards) if env.episode_rewards else [],
                information_summary={},
                reasoning_score=0.5,
                is_guessing=False,
            )

            # Analyst runs first, provides hints
            if self.analyst:
                analyst_decision = self.analyst.decide(agent_obs)
                all_decisions["analyst"].append(analyst_decision)
                analyst_hint = analyst_decision.reasoning

            # Investigator decides
            inv_decision = self.investigator.decide(agent_obs)
            all_decisions["investigator"].append(inv_decision)

            # Check if Fixer should take over based on suspicion threshold
            fixer_decision: Optional[AgentDecision] = None
            current_suspicion = self.investigator.get_suspicion()

            if current_suspicion >= self.confidence_threshold:
                fixer_decision = self.fixer.decide(agent_obs)
                all_decisions["fixer"].append(fixer_decision)
                chosen_decision = fixer_decision
            else:
                chosen_decision = inv_decision

            # Build action dict for environment
            action_dict = {
                "action_type": chosen_decision.action_type,
                "target_service": chosen_decision.target_service,
                "parameters": chosen_decision.parameters or {},
            }

            # Execute in environment
            try:
                response = env.step(action_dict)
                total_reward += response.reward

                # Update agents with outcome
                self.investigator.learn(agent_obs, inv_decision, response.reward)
                if fixer_decision:
                    self.fixer.learn(agent_obs, fixer_decision, response.reward)
                if self.analyst:
                    self.analyst.learn(agent_obs, analyst_decision, response.reward)

                # Store observation
                observations.append(response.observation)

                # Check termination
                if response.terminated or response.truncated:
                    break

            except Exception as e:  # pragma: no cover
                # If step fails, continue with next step
                continue  # pragma: no cover

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Build trajectory for grading
        trajectory = {
            "actions": [
                {"action_type": d.action_type, "target_service": d.target_service}
                for d in all_decisions["investigator"] + all_decisions["fixer"]
            ],
            "rewards": list(env.episode_rewards) if env.episode_rewards else [],
            "final_state": observations[-1] if observations else {},
            "scenario": {
                "fault_type": (
                    env.current_scenario.fault_type.value
                    if env.current_scenario else "unknown"
                ),
                "difficulty": (
                    env.current_scenario.difficulty
                    if env.current_scenario else 3
                ),
            },
        }

        # Grade the episode
        try:
            from app.enhanced_grader import grade_trajectory_enhanced
            evaluation = grade_trajectory_enhanced(
                trajectory, trajectory["scenario"], seed=seed
            )
            final_score = evaluation.breakdown.final_score
            grade = evaluation.breakdown.grade.value
        except Exception:  # pragma: no cover
            # Fallback if grading fails
            final_score = total_reward / max(len(env.episode_rewards), 1) if env.episode_rewards else 0.0  # pragma: no cover
            grade = "unknown"  # pragma: no cover

        return MultiAgentEpisodeResult(
            total_reward=round(total_reward, 3),
            final_score=round(final_score, 3),
            grade=grade,
            steps=env.current_step,
            agent_decisions=all_decisions,
            episode_id=episode_id,
            duration_ms=duration_ms,
            investigation_summary=self.investigator.get_investigation_summary(),
            fix_summary=self.fixer.get_fix_summary(),
            analysis_summary=(
                self.analyst.get_analysis_summary() if self.analyst else {}
            ),
        )

    def run_batch(
        self,
        env_factory,
        seeds: List[int],
        **kwargs
    ) -> List[MultiAgentEpisodeResult]:
        """
        Run multiple episodes with different seeds.

        Args:
            env_factory: Callable that returns a fresh IncidentEnv
            seeds: List of seeds for each episode
            **kwargs: Additional arguments for run_episode

        Returns:
            List of episode results
        """
        results = []
        for seed in seeds:
            env = env_factory(seed=seed)
            result = self.run_episode(env, seed=seed, **kwargs)
            results.append(result)
        return results

    def get_coordinator_stats(self) -> Dict[str, Any]:
        """Get overall coordinator statistics"""
        return {
            "agents": {
                "investigator": self.investigator.get_stats(),
                "fixer": self.fixer.get_stats(),
                "analyst": self.analyst.get_stats() if self.analyst else None,
            },
            "config": {
                "enable_analyst": self.enable_analyst,
                "confidence_threshold": self.confidence_threshold,
                "max_steps": self.max_steps,
            },
        }
