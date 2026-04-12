"""
IncidentOps - Unit Tests: Difficulty Guide
"""
import pytest
from app.difficulty_guide import DIFFICULTY_GUIDE


class TestDifficultyGuide:
    def test_import_succeeds(self):
        """Verify the module imports correctly."""
        assert DIFFICULTY_GUIDE is not None

    def test_has_all_5_difficulty_levels(self):
        """Verify all 5 difficulty levels are defined."""
        assert len(DIFFICULTY_GUIDE) == 5
        for level in range(1, 6):
            assert level in DIFFICULTY_GUIDE

    def test_difficulty_1_trivial(self):
        entry = DIFFICULTY_GUIDE[1]
        assert entry["name"] == "Trivial"
        assert entry["correct_action"] == "restart_service"
        assert "100%" in entry["rule_based_success"]

    def test_difficulty_2_easy(self):
        entry = DIFFICULTY_GUIDE[2]
        assert entry["name"] == "Easy"
        assert entry["correct_action"] == "restart_service"
        assert "~86%" in entry["rule_based_success"]

    def test_difficulty_3_medium(self):
        entry = DIFFICULTY_GUIDE[3]
        assert entry["name"] == "Medium"
        assert entry["correct_action"] == "scale_service (on root cause, not symptoms)"
        assert "~68%" in entry["rule_based_success"]

    def test_difficulty_4_hard(self):
        entry = DIFFICULTY_GUIDE[4]
        assert entry["name"] == "Hard"
        assert entry["correct_action"] == "restart_service (after identifying leak source)"
        assert "~43%" in entry["rule_based_success"]

    def test_difficulty_5_expert(self):
        entry = DIFFICULTY_GUIDE[5]
        assert entry["name"] == "Expert"
        assert entry["correct_action"] == "rollback_deployment (on silently corrupted service)"
        assert "~0%" in entry["rule_based_success"]

    def test_all_entries_have_required_keys(self):
        required_keys = {"name", "rule_based_success", "llm_success", "key_skill", "typical_symptoms", "correct_action"}
        for level, entry in DIFFICULTY_GUIDE.items():
            assert required_keys.issubset(entry.keys()), f"Level {level} missing keys"

    def test_all_entries_have_string_values(self):
        for level, entry in DIFFICULTY_GUIDE.items():
            for key, value in entry.items():
                assert isinstance(value, str), f"Level {level}, key {key} is not a string"