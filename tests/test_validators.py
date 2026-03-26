"""
Tests for qpopcv/validators.py

All messagebox calls are mocked so these run headless (no Tkinter window needed).
"""
import pytest
from unittest.mock import patch
from pathlib import Path

import sys

# tkinter is stubbed globally in conftest.py before this imports
from qpopcv.validators import validate_discord_core, validate_reference_image

# Grab the shared mock so we can assert on it
mb_stub = sys.modules["tkinter.messagebox"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reset_mocks():
    mb_stub.showwarning.reset_mock()
    mb_stub.showinfo.reset_mock()
    mb_stub.showerror.reset_mock()


VALID_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/sometoken"
VALID_USER_ID = "123456789012345678"  # exactly 18 digits


# ===========================================================================
# validate_discord_core
# ===========================================================================

class TestValidateDiscordCore:

    def setup_method(self):
        reset_mocks()

    # --- Happy path ---

    def test_valid_inputs_return_true(self):
        assert validate_discord_core(VALID_WEBHOOK, VALID_USER_ID) is True
        mb_stub.showwarning.assert_not_called()

    def test_leading_trailing_whitespace_is_stripped(self):
        assert validate_discord_core(f"  {VALID_WEBHOOK}  ", f"  {VALID_USER_ID}  ") is True

    # --- Webhook URL ---

    def test_empty_webhook_returns_false(self):
        assert validate_discord_core("", VALID_USER_ID) is False
        mb_stub.showwarning.assert_called_once()

    def test_whitespace_only_webhook_returns_false(self):
        assert validate_discord_core("   ", VALID_USER_ID) is False
        mb_stub.showwarning.assert_called_once()

    def test_non_discord_url_returns_false(self):
        assert validate_discord_core("https://example.com/webhook", VALID_USER_ID) is False
        mb_stub.showwarning.assert_called_once()

    def test_http_discord_url_returns_false(self):
        # Must be HTTPS
        assert validate_discord_core("http://discord.com/api/webhooks/123/token", VALID_USER_ID) is False
        mb_stub.showwarning.assert_called_once()

    def test_discord_wrong_path_returns_false(self):
        assert validate_discord_core("https://discord.com/channels/123", VALID_USER_ID) is False
        mb_stub.showwarning.assert_called_once()

    # --- User ID ---

    def test_empty_user_id_returns_false(self):
        assert validate_discord_core(VALID_WEBHOOK, "") is False
        mb_stub.showwarning.assert_called_once()

    def test_whitespace_only_user_id_returns_false(self):
        assert validate_discord_core(VALID_WEBHOOK, "   ") is False
        mb_stub.showwarning.assert_called_once()

    def test_user_id_with_letters_returns_false(self):
        assert validate_discord_core(VALID_WEBHOOK, "12345678901234567a") is False
        mb_stub.showwarning.assert_called_once()

    def test_user_id_too_short_returns_false(self):
        # 16 digits — below the 17-digit minimum
        assert validate_discord_core(VALID_WEBHOOK, "1234567890123456") is False
        mb_stub.showwarning.assert_called_once()

    def test_user_id_too_long_returns_false(self):
        # 20 digits — above the 19-digit maximum
        assert validate_discord_core(VALID_WEBHOOK, "12345678901234567890") is False
        mb_stub.showwarning.assert_called_once()

    def test_user_id_exactly_18_digits_passes(self):
        assert validate_discord_core(VALID_WEBHOOK, "1" * 18) is True

    # --- Only one warning shown per call ---

    def test_only_one_warning_per_call(self):
        # Even though both fields are wrong, only the first failure fires
        validate_discord_core("", "")
        assert mb_stub.showwarning.call_count == 1


# ===========================================================================
# validate_reference_image
# ===========================================================================

class TestValidateReferenceImage:

    def setup_method(self):
        reset_mocks()

    # --- Happy path ---

    def test_valid_existing_file_returns_true(self, tmp_path):
        img = tmp_path / "ref.png"
        img.write_bytes(b"fake image data")
        assert validate_reference_image(str(img)) is True
        mb_stub.showwarning.assert_not_called()

    def test_path_with_whitespace_is_stripped(self, tmp_path):
        img = tmp_path / "ref.png"
        img.write_bytes(b"fake image data")
        assert validate_reference_image(f"  {img}  ") is True

    # --- Failures ---

    def test_empty_string_returns_false(self):
        assert validate_reference_image("") is False
        mb_stub.showwarning.assert_called_once()

    def test_nonexistent_path_returns_false(self):
        assert validate_reference_image("/nonexistent/path/ref.png") is False
        mb_stub.showwarning.assert_called_once()

    def test_directory_path_returns_false(self, tmp_path):
        # tmp_path is a directory, not a file
        assert validate_reference_image(str(tmp_path)) is False
        mb_stub.showwarning.assert_called_once()

    def test_whitespace_only_returns_false(self):
        assert validate_reference_image("   ") is False
        mb_stub.showwarning.assert_called_once()


