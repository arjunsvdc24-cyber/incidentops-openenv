"""
IncidentOps - Baseline Agent Coverage Tests
Targets uncovered lines in app/baseline.py
"""
import pytest
from unittest.mock import MagicMock
from app.baseline import (
    BaselineAgent, AgentConfig, AgentStrategy,
    run_baseline_episode, tune_agent_performance
)
from app.environment import make_env
from app.fault_injector import FaultType


class TestBaselineAgentStrategies:
    """Test all agent strategies for full coverage"""

    def test_reset_clears_state(self):
        """Cover: baseline.py reset() method - lines 108-125"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.current_step = 5
        agent.identified_root_cause = "payment-service"
        agent.candidate_root_causes = ["api-gateway"]
        agent.action_history.append(MagicMock())
        agent.fix_applied = True

        agent.reset(seed=99)

        assert agent.current_step == 0
        assert agent.identified_root_cause is None
        assert agent.candidate_root_causes == []
        assert agent.action_history == []
        assert agent.fix_applied is False

    def test_random_strategy(self):
        """Cover: baseline.py RANDOM strategy - lines 154-155"""
        agent = BaselineAgent(AgentConfig(
            strategy=AgentStrategy.RANDOM,
            seed=42,
        ))
        obs = {
            "step": 1,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        action = agent.act(obs)
        assert "action_type" in action

    def test_memory_first_strategy(self):
        """Cover: baseline.py MEMORY_FIRST strategy - lines 156-157, 568-606"""
        agent = BaselineAgent(AgentConfig(
            strategy=AgentStrategy.MEMORY_FIRST,
            seed=42,
            use_memory=True,
        ))
        obs = {
            "step": 1,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        action = agent.act(obs)
        assert "action_type" in action
        # Should return memory lookup first
        assert agent.current_step == 1

    def test_depth_first_strategy(self):
        """Cover: baseline.py DEPTH_FIRST strategy - lines 158-159, 608-649"""
        agent = BaselineAgent(AgentConfig(
            strategy=AgentStrategy.DEPTH_FIRST,
            seed=42,
        ))
        obs = {
            "step": 1,
            "services": {"payment-service": {"status": "unhealthy"}},
            "alerts": [{"service": "payment-service", "message": "OOM"}],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        action = agent.act(obs)
        assert "action_type" in action
        assert action["target_service"] == "payment-service"

    def test_depth_first_with_healthy_services(self):
        """Cover: baseline.py DEPTH_FIRST strategy fallback when all healthy - lines 647-649"""
        agent = BaselineAgent(AgentConfig(
            strategy=AgentStrategy.DEPTH_FIRST,
            seed=42,
        ))
        obs = {
            "step": 1,
            "services": {"api-gateway": {"status": "healthy"}},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "cascade"},
        }
        action = agent.act(obs)
        assert "action_type" in action


class TestBaselineGhostScenario:
    """Test ghost scenario handling for full coverage"""

    def test_ghost_scenario_detection(self):
        """Cover: baseline.py ghost scenario - lines 282-294"""
        agent = BaselineAgent(AgentConfig(
            seed=42,
            hard_accuracy=0.45,
        ))
        obs = {
            "step": 1,
            "services": {},  # All healthy — ghost pattern
            "alerts": [],
            "incident_info": {"difficulty": 5, "fault_type": "ghost"},
            "action_result": {
                "deployments": [
                    {"service": "recommendation-service", "version": "v2.1.0",
                     "description": "algorithm optimization", "is_problematic": True},
                    {"service": "cache-service", "version": "v1.0.0",
                     "description": "bug fix", "is_problematic": False},
                ]
            },
        }
        # Take first action — should be query_deployments
        action = agent.act(obs)
        assert action["action_type"] == "query_deployments"

    def test_ghost_deployment_timeline_investigation(self):
        """Cover: baseline.py ghost phase 2.5 - lines 390-454"""
        agent = BaselineAgent(AgentConfig(
            seed=42,
            hard_accuracy=0.45,
        ))
        # Pre-populate state
        obs1 = {
            "step": 1,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 5, "fault_type": "ghost"},
            "action_result": {
                "deployments": [
                    {"service": "recommendation-service", "version": "v2.1.0",
                     "description": "optimize algorithm", "is_problematic": True},
                ]
            },
        }
        # First action: query_deployments
        agent.act(obs1)

        # Second action: should be query_dependencies
        action2 = agent.act(obs1)
        assert action2["action_type"] == "query_dependencies"

    def test_ghost_wrong_guess(self):
        """Cover: baseline.py ghost accuracy roll - lines 406-418"""
        # Use seed that causes wrong guess (roll >= hard_accuracy)
        agent = BaselineAgent(AgentConfig(
            seed=9999,  # seed for wrong roll
            hard_accuracy=0.45,
        ))
        obs = {
            "step": 3,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 5, "fault_type": "ghost"},
            "action_result": {
                "deployments": [
                    {"service": "recommendation-service", "version": "v2.1.0",
                     "description": "optimize", "is_problematic": True},
                ],
                "dependencies": {
                    "recommendation-service": ["cache-service"],
                },
                "reverse_dependencies": {
                    "cache-service": ["recommendation-service"],
                },
            },
        }
        agent.act(obs)  # query_deployments
        agent.act(obs)  # query_dependencies
        # Third action - should investigate target (metrics or logs)
        action = agent.act(obs)
        assert "action_type" in action


class TestBaselineRootCauseIdentification:
    """Test root cause identification for full coverage"""

    def test_reorder_by_dependencies_with_unhealthy(self):
        """Cover: baseline.py _reorder_by_dependencies() - lines 201-273"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.service_states = {
            "database-primary": {"status": "unhealthy"},
            "order-service": {"status": "degraded"},
            "api-gateway": {"status": "healthy"},
        }
        agent.service_graph = {
            "dependencies": {
                "order-service": ["database-primary"],
                "api-gateway": ["order-service"],
            },
            "reverse_dependencies": {
                "database-primary": ["order-service"],
                "order-service": ["api-gateway"],
            },
        }
        agent.candidate_root_causes = ["order-service", "database-primary"]

        agent._reorder_by_dependencies()

        # database-primary should come first (upstream root cause)
        assert agent.candidate_root_causes[0] == "database-primary"

    def test_reorder_ghost_no_unhealthy(self):
        """Cover: baseline.py ghost deployment timeline reordering - lines 216-248"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.service_states = {
            "recommendation-service": {"status": "healthy"},
            "cache-service": {"status": "healthy"},
        }
        agent.deploy_timeline = [
            {"service": "recommendation-service", "version": "v2.1.0",
             "description": "optimize algorithm", "is_problematic": True},
            {"service": "cache-service", "version": "v1.0.0",
             "description": "minor fix", "is_problematic": False},
        ]
        agent.candidate_root_causes = ["api-gateway"]
        # Must set service_graph non-empty so method doesn't return early
        agent.service_graph = {"dependencies": {"x": []}, "reverse_dependencies": {}}

        agent._reorder_by_dependencies()

        # recommendation-service should be first (suspicious deploy)
        assert agent.candidate_root_causes[0] == "recommendation-service"

    def test_deep_investigation_tracking(self):
        """Cover: baseline.py deep investigation - lines 360-388"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.service_states = {
            "payment-service": {"status": "degraded"},
            "order-service": {"status": "degraded"},
        }
        agent.candidate_root_causes = ["payment-service", "order-service"]
        agent.investigated_services.add("payment-service")
        agent.action_history = [
            MagicMock(action_type="query_service", target_service="payment-service"),
            MagicMock(action_type="query_metrics", target_service="payment-service"),
            MagicMock(action_type="query_dependencies", target_service=None),
            MagicMock(action_type="query_deployments", target_service=None),
        ]
        agent.service_graph = {"dependencies": {}, "reverse_dependencies": {}}

        obs = {
            "step": 3,
            "services": agent.service_states,
            "alerts": [],
            "incident_info": {"difficulty": 3, "fault_type": "cascade"},
            "action_result": {
                "dependencies": {},
                "reverse_dependencies": {},
            },
        }
        action = agent.act(obs)
        # Should return an investigation or fix action
        assert "action_type" in action

    def test_incorrect_root_cause_selection(self):
        """Cover: baseline.py wrong candidate selection - lines 536-537"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.service_states = {
            "analytics-service": {"status": "degraded"},
        }
        # Must have service_graph to avoid early return
        agent.service_graph = {"dependencies": {}, "reverse_dependencies": {}}
        agent.candidate_root_causes = ["analytics-service"]
        agent.deep_investigated.add("analytics-service")
        agent.investigated_services.add("analytics-service")
        agent.action_history = [
            MagicMock(action_type="query_service", target_service="analytics-service"),
            MagicMock(action_type="query_metrics", target_service="analytics-service"),
            MagicMock(action_type="query_logs", target_service="analytics-service"),
            MagicMock(action_type="query_dependencies", target_service=None),
            MagicMock(action_type="query_deployments", target_service=None),
        ]

        obs = {
            "step": 5,
            "services": agent.service_states,
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
            "action_result": {"dependencies": {}, "reverse_dependencies": {}},
        }
        action = agent.act(obs)
        # Should return an action (identification or fix)
        assert "action_type" in action


class TestBaselineFixApplication:
    """Test fix application for full coverage"""

    def test_fix_application_phase(self):
        """Cover: baseline.py fix application - lines 553-565"""
        agent = BaselineAgent(AgentConfig(seed=42))
        agent.identified_root_cause = "payment-service"
        agent.investigated_services.add("payment-service")
        # Must have service_graph and action_history with deps/deploys queries
        agent.service_graph = {"dependencies": {}, "reverse_dependencies": {}}
        agent.action_history = [
            MagicMock(action_type="query_dependencies", target_service=None),
            MagicMock(action_type="query_deployments", target_service=None),
        ]

        obs = {
            "step": 6,
            "services": {"payment-service": {"status": "degraded"}},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
            "action_result": {},
        }
        action = agent.act(obs)
        # Should return a valid action
        assert "action_type" in action

    def test_memory_query_in_systematic(self):
        """Cover: baseline.py memory query - lines 317-322"""
        agent = BaselineAgent(AgentConfig(
            seed=42,
            use_memory=True,
        ))
        obs = {
            "step": 0,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        action = agent.act(obs)
        assert "action_type" in action


class TestBaselineEpisode:
    """Test baseline episode execution for full coverage"""

    def test_run_baseline_episode(self):
        """Cover: baseline.py run_baseline_episode - lines 676-776"""
        env = make_env(seed=42, fault_type=FaultType.OOM, difficulty=2)
        agent = BaselineAgent(AgentConfig(seed=42))
        result = run_baseline_episode(env, agent, seed=42, max_steps=5, verbose=False)
        env.close()

        assert "steps" in result
        assert "final_score" in result
        assert "grade" in result
        assert result["steps"] > 0
        assert 0.0 <= result["final_score"] <= 1.0

    def test_run_baseline_episode_verbose(self):
        """Cover: baseline.py run_baseline_episode verbose path - lines 706-712, 759-767"""
        env = make_env(seed=42, fault_type=FaultType.CASCADE, difficulty=3)
        agent = BaselineAgent(AgentConfig(seed=42))
        result = run_baseline_episode(env, agent, seed=42, max_steps=10, verbose=True)
        env.close()

        assert result["final_score"] >= 0.0
        assert result["grade"] in ["expert", "proficient", "competent", "learning", "novice"]


class TestBaselineTuning:
    """Test agent tuning for full coverage"""

    def test_tune_agent_performance(self):
        """Cover: baseline.py tune_agent_performance - lines 779-839"""
        results = tune_agent_performance(
            target_easy=0.85,
            target_medium=0.55,
            target_hard=0.25,
            num_episodes=2,
            verbose=False,
        )

        assert "easy" in results
        assert "medium" in results
        assert "hard" in results
        assert "average" in results["easy"]
        assert "average" in results["medium"]
        assert "average" in results["hard"]

    def test_get_action_log(self):
        """Cover: baseline.py get_action_log() - lines 651-662"""
        agent = BaselineAgent(AgentConfig(seed=42))
        obs = {
            "step": 1,
            "services": {"api-gateway": {"status": "healthy"}},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        agent.act(obs)
        log = agent.get_action_log()
        assert len(log) == 1
        assert "step" in log[0]
        assert "action" in log[0]

    def test_get_summary(self):
        """Cover: baseline.py get_summary() - line 664-673"""
        agent = BaselineAgent(AgentConfig(seed=42))
        obs = {
            "step": 1,
            "services": {},
            "alerts": [],
            "incident_info": {"difficulty": 2, "fault_type": "oom"},
        }
        agent.act(obs)
        summary = agent.get_summary()
        assert "total_steps" in summary
        assert "services_investigated" in summary
        assert "root_cause_identified" in summary
        assert summary["strategy"] == "systematic"
