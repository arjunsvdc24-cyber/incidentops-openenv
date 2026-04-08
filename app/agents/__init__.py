"""
IncidentOps - Multi-Agent RL System

Provides:
- Base agent classes for role-based agents
- Investigator, Fixer, Analyst specialized agents
- AgentCoordinator for multi-agent collaboration
- Stable-Baselines3 Gymnasium wrapper and trainer
"""
from app.agents.base import BaseAgent, AgentRole, AgentObservation, AgentDecision
from app.agents.investigator import InvestigatorAgent
from app.agents.fixer import FixerAgent
from app.agents.analyst import AnalystAgent
from app.agents.coordinator import AgentCoordinator, MultiAgentEpisodeResult
from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

__all__ = [
    "BaseAgent",
    "AgentRole",
    "AgentObservation",
    "AgentDecision",
    "InvestigatorAgent",
    "FixerAgent",
    "AnalystAgent",
    "AgentCoordinator",
    "MultiAgentEpisodeResult",
    "RLTrainer",
    "GymnasiumWrapper",
]
