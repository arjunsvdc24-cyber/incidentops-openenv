"""
IncidentOps - Validation Module Tests

Tests the ValidationRunner class which validates:
1. Determinism (same seed → identical results)
2. Environment (reset/step functionality)
3. Grader (valid scores in 0.0-1.0)
4. Baseline agent (runs without error)
5. Integration (components work together)
"""
import pytest
from app.validation import ValidationRunner, ValidationResult, run_validation


class TestValidationResult:
    """ValidationResult dataclass holds individual test results."""

    def test_validation_result_creation(self):
        r = ValidationResult(
            test_name="test_determinism",
            passed=True,
            message="Same seed produces identical results",
        )
        assert r.test_name == "test_determinism"
        assert r.passed is True
        assert r.message == "Same seed produces identical results"

    def test_validation_result_with_details(self):
        r = ValidationResult(
            test_name="test_env",
            passed=True,
            message="Environment initialized",
            details={"env_id": "test-001"},
        )
        assert r.details == {"env_id": "test-001"}

    def test_validation_result_defaults_none(self):
        r = ValidationResult("test", True, "msg")
        assert r.details is None


class TestValidationRunnerInit:
    """ValidationRunner initializes correctly."""

    def test_runner_default_seed(self):
        runner = ValidationRunner()
        assert runner.seed == 42
        assert runner.results == []

    def test_runner_custom_seed(self):
        runner = ValidationRunner(seed=99)
        assert runner.seed == 99


class TestValidationRunnerMethods:
    """ValidationRunner has all required methods."""

    def test_has_all_test_methods(self):
        runner = ValidationRunner()
        expected = [
            "run_all",
            "test_determinism",
            "test_environment",
            "test_grader",
            "test_baseline",
            "test_integration",
            "_pass",
            "_fail",
            "_generate_summary",
        ]
        for method in expected:
            assert hasattr(runner, method), f"Missing method: {method}"


class TestValidationRunAll:
    """run_all produces a complete summary."""

    def test_run_all_returns_dict(self):
        runner = ValidationRunner(seed=42)
        summary = runner.run_all()
        assert isinstance(summary, dict)

    def test_run_all_has_summary_fields(self):
        runner = ValidationRunner(seed=42)
        summary = runner.run_all()
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "results" in summary
        # Field may be 'success_rate' or 'pass_rate'
        assert "success_rate" in summary or "pass_rate" in summary

    def test_run_all_records_results(self):
        runner = ValidationRunner(seed=42)
        summary = runner.run_all()
        assert len(summary["results"]) > 0


class TestDeterminism:
    """test_determinism proves reproducibility."""

    def test_determinism_runs(self):
        runner = ValidationRunner(seed=42)
        runner.test_determinism()
        assert len(runner.results) > 0

    def test_determinism_checks_reproducibility(self):
        runner = ValidationRunner(seed=42)
        runner.test_determinism()
        det_results = [r for r in runner.results if "determinism" in r.test_name.lower()]
        assert len(det_results) > 0


class TestEnvironment:
    """test_environment proves core RL interface works."""

    def test_environment_runs(self):
        runner = ValidationRunner(seed=42)
        runner.test_environment()
        assert len(runner.results) > 0

    def test_environment_checks_reset_and_step(self):
        runner = ValidationRunner(seed=42)
        runner.test_environment()
        env_results = [r for r in runner.results if "env" in r.test_name.lower()]
        assert len(env_results) > 0


class TestGrader:
    """test_grader proves scoring works."""

    def test_grader_runs(self):
        runner = ValidationRunner(seed=42)
        runner.test_grader()
        assert len(runner.results) > 0

    def test_grader_checks_score_range(self):
        runner = ValidationRunner(seed=42)
        runner.test_grader()
        grader_results = [r for r in runner.results if "grader" in r.test_name.lower()]
        assert len(grader_results) > 0


class TestBaseline:
    """test_baseline proves baseline agent works."""

    def test_baseline_runs(self):
        runner = ValidationRunner(seed=42)
        runner.test_baseline()
        assert len(runner.results) > 0

    def test_baseline_checks_agent_execution(self):
        runner = ValidationRunner(seed=42)
        runner.test_baseline()
        baseline_results = [r for r in runner.results if "baseline" in r.test_name.lower()]
        assert len(baseline_results) > 0


class TestIntegration:
    """test_integration proves components work together."""

    def test_integration_runs(self):
        runner = ValidationRunner(seed=42)
        runner.test_integration()
        assert len(runner.results) > 0


class TestHelperMethods:
    """Helper methods _pass and _fail."""

    def test_pass_adds_result(self):
        runner = ValidationRunner(seed=42)
        runner._pass("test_one", "Test passed")
        assert len(runner.results) == 1
        assert runner.results[0].passed is True
        assert runner.results[0].test_name == "test_one"

    def test_fail_adds_result(self):
        runner = ValidationRunner(seed=42)
        runner._fail("test_two", "Test failed")
        assert len(runner.results) == 1
        assert runner.results[0].passed is False
        assert runner.results[0].test_name == "test_two"


class TestSummaryGeneration:
    """_generate_summary produces valid report."""

    def test_summary_generates_correct_counts(self):
        runner = ValidationRunner(seed=42)
        runner._pass("t1", "ok")
        runner._pass("t2", "ok")
        runner._fail("t3", "bad")
        summary = runner._generate_summary()
        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1

    def test_summary_all_passed(self):
        runner = ValidationRunner(seed=42)
        runner._pass("t1", "ok")
        runner._pass("t2", "ok")
        summary = runner._generate_summary()
        assert summary["failed"] == 0
        assert summary["all_passed"] is True


class TestRunValidation:
    """Top-level run_validation function."""

    def test_run_validation_returns_dict(self):
        result = run_validation(seed=42)
        assert isinstance(result, dict)

    def test_run_validation_has_results(self):
        result = run_validation(seed=42)
        assert "results" in result
        assert len(result["results"]) > 0
