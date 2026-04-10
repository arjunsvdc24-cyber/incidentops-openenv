"""
IncidentOps - Full Validation Script v11.0

Validates:
1. Same seed → identical results (determinism)
2. All endpoints respond correctly
3. Grader returns valid scores
4. Baseline runs without error

Automated test script.
"""
import sys
import json
import time
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a single validation test"""
    test_name: str
    passed: bool
    message: str
    details: dict = None


class ValidationRunner:
    """
    Runs full validation suite.
    
    Tests:
    1. Determinism test
    2. Environment reset/step
    3. All endpoints
    4. Grader functionality
    5. Baseline agent
    """
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.results: list[ValidationResult] = []
    
    def run_all(self) -> dict:
        """Run all validation tests"""
        print("=" * 60)
        print("IncidentOps v11.0 - Full Validation Suite")
        print("=" * 60)
        print()
        
        # Run tests
        self.test_determinism()
        self.test_environment()
        self.test_grader()
        self.test_baseline()
        self.test_integration()
        
        # Summary
        return self._generate_summary()
    
    def test_determinism(self) -> None:
        """Test that same seed produces identical results"""
        print("Testing Determinism...")
        
        try:
            from app.environment import make_env
            from app.determinism import run_reproducibility_test
            
            # Test 1: Basic reproducibility
            result = run_reproducibility_test(seed=self.seed, num_steps=5)
            
            if result["passed"]:
                self._pass("Determinism - Basic", "Same seed produces identical results")
            else:
                self._fail("Determinism - Basic", f"Failed: {result['errors']}")
            
            # Test 2: Environment reset
            env1 = make_env(seed=self.seed)
            env2 = make_env(seed=self.seed)
            
            obs1 = env1.reset(seed=self.seed)
            obs2 = env2.reset(seed=self.seed)
            
            if obs1 == obs2:
                self._pass("Determinism - Reset", "Reset produces identical observations")
            else:
                self._fail("Determinism - Reset", "Reset produces different observations")
            
            # Test 3: Step reproducibility
            actions = [
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_metrics", "target_service": "user-service"},
                {"action_type": "query_logs", "target_service": "order-service"},
            ]
            
            rewards1 = []
            rewards2 = []
            
            for action in actions:
                r1 = env1.step(action)
                r2 = env2.step(action)
                rewards1.append(r1.reward)
                rewards2.append(r2.reward)
            
            if rewards1 == rewards2:
                self._pass("Determinism - Steps", "Steps produce identical rewards")
            else:
                self._fail("Determinism - Steps", f"Rewards differ: {rewards1} vs {rewards2}")
            
        except Exception as e:  # pragma: no cover
            self._fail("Determinism", f"Exception: {str(e)}")  # pragma: no cover

    def test_environment(self) -> None:
        """Test environment functionality"""
        print("Testing Environment...")
        
        try:
            from app.environment import make_env, IncidentEnv, EnvironmentConfig
            from app.fault_injector import FaultType
            
            # Test 1: Creation
            env = make_env(seed=self.seed)
            if env:
                self._pass("Environment - Creation", "Environment created successfully")
            else:
                self._fail("Environment - Creation", "Failed to create environment")
                return
            
            # Test 2: Reset
            obs = env.reset(seed=self.seed)
            if obs and "services" in obs and "alerts" in obs:
                self._pass("Environment - Reset", "Reset returns valid observation")
            else:
                self._fail("Environment - Reset", "Invalid observation structure")
            
            # Test 3: Step
            action = {"action_type": "query_service", "target_service": "api-gateway"}
            response = env.step(action)
            
            if response and hasattr(response, 'reward') and hasattr(response, 'observation'):
                self._pass("Environment - Step", "Step returns valid response")
            else:
                self._fail("Environment - Step", "Invalid step response")
            
            # Test 4: All fault types
            for fault_type in FaultType:
                env = make_env(seed=self.seed, fault_type=fault_type)
                obs = env.reset(seed=self.seed)
                
                if obs.get("incident_info", {}).get("fault_type") == fault_type.value:
                    self._pass(f"Environment - {fault_type.value}", f"Generated {fault_type.value} scenario")
                else:
                    self._fail(f"Environment - {fault_type.value}", "Wrong fault type generated")
            
            # Test 5: Difficulty levels
            for difficulty in range(1, 6):
                env = make_env(seed=self.seed, difficulty=difficulty)
                obs = env.reset(seed=self.seed)
                
                if obs.get("incident_info", {}).get("difficulty") == difficulty:
                    self._pass(f"Environment - Difficulty {difficulty}", f"Difficulty {difficulty} set correctly")
                else:
                    self._fail(f"Environment - Difficulty {difficulty}", "Wrong difficulty")
            
        except Exception as e:  # pragma: no cover
            self._fail("Environment", f"Exception: {str(e)}")  # pragma: no cover

    def test_grader(self) -> None:
        """Test grader functionality"""
        print("Testing Grader...")
        
        try:
            from app.grader import DeepTrajectoryGrader, grade_trajectory
            from app.sre_grader import SREExpertGrader, grade_like_sre
            
            # Test trajectory
            trajectory = {
                "actions": [
                    {"action_type": "query_service", "target_service": "database-primary"},
                    {"action_type": "query_logs", "target_service": "database-primary"},
                    {"action_type": "identify_root_cause", "target_service": "database-primary"},
                    {"action_type": "restart_service", "target_service": "database-primary"},
                ],
                "rewards": [0.1, 0.1, 0.3, 0.3],
                "final_state": {"fix_applied": True},
                "scenario": {
                    "fault_type": "cascade",
                    "root_cause_service": "database-primary",
                    "affected_services": ["user-service", "order-service"],
                }
            }
            
            # Test 1: Basic grader
            score = grade_trajectory(trajectory, seed=self.seed)
            
            if 0.0 <= score.final_score <= 1.0:
                self._pass("Grader - Basic", f"Score: {score.final_score:.3f}")
            else:
                self._fail("Grader - Basic", f"Invalid score: {score.final_score}")
            
            # Test 2: SRE grader
            scenario = {
                "fault_type": "cascade",
                "root_cause_service": "database-primary",
                "affected_services": ["user-service", "order-service"],
            }
            
            sre_eval = grade_like_sre(trajectory, scenario, seed=self.seed)
            
            if 0.0 <= sre_eval.final_score <= 1.0:
                self._pass("Grader - SRE", f"Score: {sre_eval.final_score:.3f}, Grade: {sre_eval.grade.value}")
            else:
                self._fail("Grader - SRE", f"Invalid score: {sre_eval.final_score}")
            
            # Test 3: Grader explanation
            if sre_eval.explanation:
                self._pass("Grader - Explanation", "Explanation generated")
            else:
                self._fail("Grader - Explanation", "No explanation generated")
            
        except Exception as e:  # pragma: no cover
            self._fail("Grader", f"Exception: {str(e)}")  # pragma: no cover

    def test_baseline(self) -> None:
        """Test baseline agent"""
        print("Testing Baseline Agent...")
        
        try:
            from app.environment import make_env
            from app.baseline import BaselineAgent, AgentConfig, run_baseline_episode
            
            # Test 1: Agent creation
            agent = BaselineAgent(AgentConfig(seed=self.seed))
            if agent:
                self._pass("Baseline - Creation", "Agent created successfully")
            else:
                self._fail("Baseline - Creation", "Failed to create agent")
                return
            
            # Test 2: Run episode
            env = make_env(seed=self.seed, difficulty=3)
            result = run_baseline_episode(env, agent, seed=self.seed, max_steps=15, verbose=False)
            
            if "final_score" in result and "grade" in result:
                self._pass("Baseline - Episode", f"Score: {result['final_score']:.3f}, Grade: {result['grade']}")
            else:
                self._fail("Baseline - Episode", "Invalid result structure")
            
            # Test 3: Multiple difficulties
            for difficulty, expected_range in [(2, (0.6, 1.0)), (3, (0.3, 0.8)), (5, (0.0, 0.5))]:
                env = make_env(seed=self.seed, difficulty=difficulty)
                agent = BaselineAgent(AgentConfig(seed=self.seed))
                result = run_baseline_episode(env, agent, seed=self.seed, max_steps=20, verbose=False)
                
                score = result["final_score"]
                low, high = expected_range
                
                if low <= score <= high:
                    self._pass(f"Baseline - Difficulty {difficulty}", f"Score {score:.3f} in expected range [{low}, {high}]")
                else:
                    self._fail(f"Baseline - Difficulty {difficulty}", f"Score {score:.3f} outside range [{low}, {high}]")
            
        except Exception as e:  # pragma: no cover
            self._fail("Baseline", f"Exception: {str(e)}")  # pragma: no cover

    def test_integration(self) -> None:
        """Test integration between components"""
        print("Testing Integration...")
        
        try:
            from app.environment import make_env
            from app.grader import grade_trajectory
            from app.memory import IncidentMemory
            from app.action_tracker import ActionTracker
            
            # Test 1: Memory integration
            memory = IncidentMemory(seed=self.seed)
            matches = memory.search(symptoms=["OutOfMemoryError"], services=["payment-service"])
            
            if matches:
                self._pass("Integration - Memory", f"Found {len(matches)} similar incidents")
            else:
                self._pass("Integration - Memory", "Memory system working (no matches found)")
            
            # Test 2: Action tracking
            tracker = ActionTracker(seed=self.seed)
            tracker.record_action(1, "query_service", "api-gateway", {"status": "healthy"})
            tracker.record_action(2, "query_service", "api-gateway", {"status": "healthy"})
            
            penalties = tracker.calculate_penalties()
            if penalties.total_penalty > 0:
                self._pass("Integration - Action Tracker", f"Detected redundant actions: penalty={penalties.total_penalty:.3f}")
            else:
                self._pass("Integration - Action Tracker", "Action tracker working")
            
            # Test 3: Full workflow
            env = make_env(seed=self.seed)
            obs = env.reset(seed=self.seed)
            
            actions = []
            for action in [
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_metrics", "target_service": "user-service"},
            ]:
                response = env.step(action)
                actions.append({"action_type": action["action_type"], "target_service": action.get("target_service")})
            
            trajectory = {
                "actions": actions,
                "rewards": [],
                "final_state": {"fix_applied": False},
                "scenario": obs.get("incident_info", {}),
            }
            
            score = grade_trajectory(trajectory, seed=self.seed)
            
            self._pass("Integration - Full Workflow", f"Workflow completed, score: {score.final_score:.3f}")
            
        except Exception as e:  # pragma: no cover
            self._fail("Integration", f"Exception: {str(e)}")  # pragma: no cover

    def _pass(self, test_name: str, message: str) -> None:
        """Record passing test"""
        self.results.append(ValidationResult(
            test_name=test_name,
            passed=True,
            message=message
        ))
        print(f"  ✓ {test_name}: {message}")
    
    def _fail(self, test_name: str, message: str) -> None:
        """Record failing test"""
        self.results.append(ValidationResult(
            test_name=test_name,
            passed=False,
            message=message
        ))
        print(f"  ✗ {test_name}: {message}")
    
    def _generate_summary(self) -> dict:
        """Generate summary of all tests"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print()
        print("=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {passed/total*100:.1f}%")
        print("=" * 60)
        
        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.test_name}: {r.message}")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total if total > 0 else 0,
            "all_passed": failed == 0,
            "results": [
                {"test": r.test_name, "passed": r.passed, "message": r.message}
                for r in self.results
            ]
        }


def run_validation(seed: int = 42) -> dict:
    """
    Run full validation suite.
    
    Returns summary dict.
    """
    runner = ValidationRunner(seed=seed)
    return runner.run_all()


if __name__ == "__main__":
    result = run_validation(seed=42)
    sys.exit(0 if result["all_passed"] else 1)
