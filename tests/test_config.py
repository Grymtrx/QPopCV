"""
Tests for qpopcv/config.py

Uses tmp_path (pytest fixture) for all file I/O so nothing touches the real config.json.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# We patch CONFIG_PATH before each test so the module never reads/writes the
# real config.json on disk.
# ---------------------------------------------------------------------------

from qpopcv import config as cfg_module
from qpopcv.config import DEFAULT_CONFIG, load_config, save_config


def make_config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


# ===========================================================================
# load_config
# ===========================================================================

class TestLoadConfig:

    def test_returns_defaults_when_file_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch.object(cfg_module, "CONFIG_PATH", fake_path):
            result = load_config()
        assert result["check_interval"] == DEFAULT_CONFIG["check_interval"]
        assert result["confidence"] == DEFAULT_CONFIG["confidence"]

    def test_merges_file_over_defaults(self, tmp_path):
        config_file = make_config_path(tmp_path)
        config_file.write_text(json.dumps({"user_id": "123456789012345678"}), encoding="utf-8")
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            result = load_config()
        # User-supplied value overrides default
        assert result["user_id"] == "123456789012345678"
        # Default values still present
        assert "check_interval" in result
        assert "confidence" in result

    def test_returns_defaults_on_corrupt_json(self, tmp_path):
        config_file = make_config_path(tmp_path)
        config_file.write_text("{ this is not valid json !!!", encoding="utf-8")
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            result = load_config()
        assert result == DEFAULT_CONFIG

    def test_returns_copy_not_reference(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch.object(cfg_module, "CONFIG_PATH", fake_path):
            r1 = load_config()
            r2 = load_config()
        r1["user_id"] = "mutated"
        assert r2["user_id"] != "mutated"

    def test_all_default_keys_present(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch.object(cfg_module, "CONFIG_PATH", fake_path):
            result = load_config()
        for key in DEFAULT_CONFIG:
            assert key in result, f"Missing key: {key}"

    def test_extra_keys_in_file_are_preserved(self, tmp_path):
        config_file = make_config_path(tmp_path)
        config_file.write_text(json.dumps({"custom_key": "hello"}), encoding="utf-8")
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            result = load_config()
        assert result.get("custom_key") == "hello"


# ===========================================================================
# save_config
# ===========================================================================

class TestSaveConfig:

    def test_writes_valid_json(self, tmp_path):
        config_file = make_config_path(tmp_path)
        data = {"webhook_url": "https://example.com", "user_id": "123456789012345678"}
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            save_config(data)
        raw = config_file.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert parsed == data

    def test_round_trip(self, tmp_path):
        config_file = make_config_path(tmp_path)
        original = DEFAULT_CONFIG.copy()
        original["user_id"] = "999999999999999999"
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            save_config(original)
            loaded = load_config()
        assert loaded["user_id"] == "999999999999999999"

    def test_overwrites_existing_file(self, tmp_path):
        config_file = make_config_path(tmp_path)
        config_file.write_text(json.dumps({"old": "data"}), encoding="utf-8")
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            save_config({"new": "data"})
        parsed = json.loads(config_file.read_text(encoding="utf-8"))
        assert "old" not in parsed
        assert parsed["new"] == "data"

    def test_output_is_indented(self, tmp_path):
        config_file = make_config_path(tmp_path)
        with patch.object(cfg_module, "CONFIG_PATH", config_file):
            save_config({"a": 1})
        raw = config_file.read_text(encoding="utf-8")
        # Indented JSON contains newlines
        assert "\n" in raw
