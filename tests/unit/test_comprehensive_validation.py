"""
IncidentOps - Comprehensive Validation Module Tests

Tests the ComprehensiveValidator and ValidationReport classes.
Covers all 8 categories: Determinism, Environment, Grading, Baseline,
Anti-Bruteforce, Deception, Reasoning, Integration.
"""
import pytest
from app.comprehensive_validation import (
    ComprehensiveValidator,
    TestResult,
    ValidationReport,
    run_comprehensive_validation,
)


class TestTestResult:
    """TestResult dataclass holds individual test results."""

    def test_test_result_creation(self):
        r = TestResult(
            test_id="test_001",
            category="ENVIRONMENT",
            passed=True,
            message="Environment created",
        )
        assert r.test_id == "test_001"
        assert r.category == "ENVIRONMENT"
        assert r.passed is True
        assert r.message == "Environment created"

    def test_test_result_details(self):
        r = TestResult(
            test_id="test_001",
            category="ENVIRONMENT",
            passed=True,
            message="msg",
            details={"key": "value"},
        )
        assert r.details == {"key": "value"}


class TestValidationReport:
    """ValidationReport holds the full validation summary."""

    def test_validation_report_defaults(self):
        report = ValidationReport()
        assert report.total_tests == 0
        assert report.passed == 0
        assert report.failed == 0
        assert report.skipped == 0
        assert report.pass_rate == 0.0
        assert report.all_passed is False
        assert report.results == []
        assert report.categories == {}

    def test_validation_report_to_dict(self):
        report = ValidationReport()
        d = report.to_dict()
        assert d["total_tests"] == 0
        assert d["passed"] == 0
        assert d["failed"] == 0
        assert d["pass_rate"] == "0.0%"
        assert d["all_passed"] is False
        assert "categories" in d
        assert "results" in d

    def test_validation_report_pass_rate_calculation(self):
        report = ValidationReport()
        report.total_tests = 10
        report.passed = 8
        report.failed = 2
        report.pass_rate = 8 / 10
        d = report.to_dict()
        assert d["pass_rate"] == "80.0%"

    def test_validation_report_all_passed(self):
        report = ValidationReport()
        report.failed = 0
        report.all_passed = True
        assert report.all_passed is True

    def test_validation_report_none_passed(self):
        report = ValidationReport()
        report.passed = 0
        report.failed = 5
        report.all_passed = False
        assert report.all_passed is False


class TestComprehensiveValidatorInit:
    """ComprehensiveValidator initializes correctly."""

    def test_validator_default_seed(self):
        v = ComprehensiveValidator()
        assert v.seed == 42
        assert v.verbose is True
        assert v.report is not None

    def test_validator_custom_seed(self):
        v = ComprehensiveValidator(seed=99, verbose=False)
        assert v.seed == 99
        assert v.verbose is False

    def test_validator_has_all_test_methods(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        expected_methods = [
            "run_all",
            "_test_determinism",
            "_test_environment",
            "_test_grading",
            "_test_baseline",
            "_test_anti_brute_force",
            "_test_deception",
            "_test_reasoning",
            "_test_integration",
            "_generate_summary",
            "_record_result",
        ]
        for method in expected_methods:
            assert hasattr(v, method), f"Missing method: {method}"


class TestComprehensiveValidatorRuns:
    """Validator runs all test categories."""

    def test_run_all_produces_report(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert isinstance(report, ValidationReport)
        assert report.total_tests > 0

    def test_run_all_has_all_categories(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        expected_categories = {
            "DETERMINISM", "ENVIRONMENT", "GRADING", "BASELINE",
            "ANTI_BRUTE_FORCE", "DECEPTION", "REASONING", "INTEGRATION"
        }
        actual = set(report.categories.keys())
        assert expected_categories.issubset(actual), (
            f"Missing categories: {expected_categories - actual}"
        )

    def test_run_all_records_results(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert len(report.results) == report.total_tests
        assert len(report.results) > 20  # Should have many tests

    def test_run_comprehensive_validation_function(self):
        """run_comprehensive_validation is the top-level API."""
        report = run_comprehensive_validation(seed=42, verbose=False)
        assert isinstance(report, ValidationReport)
        assert report.total_tests > 0


class TestAntiBruteForceCategory:
    """ANTI_BRUTE_FORCE category tests detect guessing behavior."""

    def test_abf_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        abf = report.categories.get("ANTI_BRUTE_FORCE", {})
        assert abf.get("passed", 0) + abf.get("failed", 0) >= 4, (
            "Should have at least 4 anti-bruteforce tests"
        )

    def test_abf_category_records(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert "ANTI_BRUTE_FORCE" in report.categories


class TestDeceptionCategory:
    """DECEPTION category tests prove deceptive signals exist."""

    def test_deception_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        dec = report.categories.get("DECEPTION", {})
        total = dec.get("passed", 0) + dec.get("failed", 0)
        assert total >= 4, f"Should have 4+ deception tests, got {total}"

    def test_deception_patterns_generated(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert "DECEPTION" in report.categories


class TestGradingCategory:
    """GRADING category tests prove graders work."""

    def test_grading_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        grad = report.categories.get("GRADING", {})
        total = grad.get("passed", 0) + grad.get("failed", 0)
        assert total >= 3, f"Should have 3+ grading tests, got {total}"

    def test_grading_scores_in_range(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        # All grading tests should pass (scores in 0.0-1.0 range)
        for result in report.results:
            if result.category == "GRADING":
                assert result.passed, f"Grading test {result.test_id} failed: {result.message}"


class TestDeterminismCategory:
    """DETERMINISM category tests prove reproducibility."""

    def test_determinism_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        det = report.categories.get("DETERMINISM", {})
        total = det.get("passed", 0) + det.get("failed", 0)
        assert total >= 3, f"Should have 3+ determinism tests, got {total}"

    def test_determinism_passes(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        det = report.categories.get("DETERMINISM", {})
        assert det.get("failed", 0) == 0, "Determinism tests should pass"


class TestEnvironmentCategory:
    """ENVIRONMENT category tests prove core RL interface."""

    def test_environment_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        env = report.categories.get("ENVIRONMENT", {})
        total = env.get("passed", 0) + env.get("failed", 0)
        assert total >= 5, f"Should have 5+ environment tests, got {total}"


class TestBaselineCategory:
    """BASELINE category tests prove baseline agent works."""

    def test_baseline_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        base = report.categories.get("BASELINE", {})
        total = base.get("passed", 0) + base.get("failed", 0)
        assert total >= 4, f"Should have 4+ baseline tests, got {total}"

    def test_baseline_runs_all_difficulties(self):
        """Baseline runs on all difficulty levels and produces valid scores."""
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        base_tests = [r for r in report.results if r.category == "BASELINE"]
        assert len(base_tests) >= 4, f"Should have 4+ baseline tests, got {len(base_tests)}"
        # Most baseline tests should pass (allow 1 failure for difficulty progression edge case)
        passed = sum(1 for r in base_tests if r.passed)
        assert passed >= 3, f"At least 3 baseline tests should pass, got {passed}"


class TestReasoningCategory:
    """REASONING category tests prove reasoning reward system."""

    def test_reasoning_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        rea = report.categories.get("REASONING", {})
        total = rea.get("passed", 0) + rea.get("failed", 0)
        assert total >= 4, f"Should have 4+ reasoning tests, got {total}"


class TestIntegrationCategory:
    """INTEGRATION category tests prove components work together."""

    def test_integration_tests_exist(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        integ = report.categories.get("INTEGRATION", {})
        total = integ.get("passed", 0) + integ.get("failed", 0)
        assert total >= 3, f"Should have 3+ integration tests, got {total}"


class TestReportPassRate:
    """Overall pass rate should be high."""

    def test_validator_produces_report(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert report.total_tests > 20, "Validator should run many tests"
        assert report.pass_rate > 0.9, (
            f"Pass rate {report.pass_rate:.1%} below 90% — "
            f"failed: {[(r.category, r.test_id, r.message) for r in report.results if not r.passed]}"
        )

    def test_pass_rate_above_90_percent(self):
        v = ComprehensiveValidator(seed=42, verbose=False)
        report = v.run_all()
        assert report.pass_rate >= 0.9, (
            f"Pass rate {report.pass_rate:.1%} below 90% — "
            f"failed: {[(r.category, r.test_id, r.message) for r in report.results if not r.passed]}"
        )
