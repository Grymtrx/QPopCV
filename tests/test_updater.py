"""
Tests for qpopcv/updater.py

All network calls are mocked — no real HTTP requests are made.
All file-system operations use tmp_path.
"""
import json
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# tkinter is stubbed globally in conftest.py
from qpopcv.updater import UpdateManager, UpdateInfo


# ===========================================================================
# Helpers
# ===========================================================================

def make_manager(current_version="1.0.0", app_dir=None) -> UpdateManager:
    return UpdateManager(
        repo_owner="Grymtrx",
        repo_name="QPopCV",
        current_version=current_version,
        app_dir=app_dir,
    )


def fake_release_response(tag="v2.0.0", zip_url="https://example.com/update.zip"):
    """Build a minimal GitHub releases/latest JSON payload."""
    return {
        "tag_name": tag,
        "html_url": "https://github.com/Grymtrx/QPopCV/releases/tag/v2.0.0",
        "name": "Release 2.0.0",
        "assets": [
            {"browser_download_url": zip_url}
        ],
        "zipball_url": "https://api.github.com/repos/Grymtrx/QPopCV/zipball/v2.0.0",
    }


# ===========================================================================
# _normalize_tag
# ===========================================================================

class TestNormalizeTag:

    def test_strips_v_prefix(self):
        assert UpdateManager._normalize_tag("v1.2.3") == "1.2.3"

    def test_strips_release_prefix(self):
        assert UpdateManager._normalize_tag("release-1.2.3") == "1.2.3"

    def test_plain_version(self):
        assert UpdateManager._normalize_tag("1.2.3") == "1.2.3"

    def test_empty_string_returns_empty(self):
        assert UpdateManager._normalize_tag("") == ""

    def test_single_digit(self):
        assert UpdateManager._normalize_tag("v3") == "3"


# ===========================================================================
# _normalize_version / _is_newer_version
# ===========================================================================

class TestVersionComparison:

    def _is_newer(self, latest, current):
        mgr = make_manager()
        return mgr._is_newer_version(latest, current)

    def test_newer_major(self):
        assert self._is_newer("2.0.0", "1.0.0") is True

    def test_newer_minor(self):
        assert self._is_newer("1.1.0", "1.0.0") is True

    def test_newer_patch(self):
        assert self._is_newer("1.0.1", "1.0.0") is True

    def test_same_version_not_newer(self):
        assert self._is_newer("1.0.0", "1.0.0") is False

    def test_older_not_newer(self):
        assert self._is_newer("0.9.9", "1.0.0") is False

    def test_older_major_not_newer(self):
        assert self._is_newer("1.0.0", "2.0.0") is False

    def test_multi_digit_components(self):
        assert self._is_newer("1.10.0", "1.9.0") is True

    def test_current_104_latest_105(self):
        """Regression test matching actual app version."""
        assert self._is_newer("1.0.5", "1.0.4") is True

    def test_current_104_latest_104_not_newer(self):
        assert self._is_newer("1.0.4", "1.0.4") is False


# ===========================================================================
# _select_download_url
# ===========================================================================

class TestSelectDownloadUrl:

    def test_prefers_zip_asset(self):
        data = {
            "assets": [{"browser_download_url": "https://example.com/release.zip"}],
            "zipball_url": "https://fallback.com/zipball",
        }
        assert UpdateManager._select_download_url(data) == "https://example.com/release.zip"

    def test_falls_back_to_zipball_when_no_zip_asset(self):
        data = {
            "assets": [{"browser_download_url": "https://example.com/release.exe"}],
            "zipball_url": "https://fallback.com/zipball",
        }
        assert UpdateManager._select_download_url(data) == "https://fallback.com/zipball"

    def test_returns_none_when_no_assets_and_no_zipball(self):
        data = {"assets": [], "zipball_url": None}
        assert UpdateManager._select_download_url(data) is None

    def test_empty_assets_list_falls_back_to_zipball(self):
        data = {"assets": [], "zipball_url": "https://fallback.com/zipball"}
        assert UpdateManager._select_download_url(data) == "https://fallback.com/zipball"

    def test_ignores_non_zip_assets(self):
        data = {
            "assets": [
                {"browser_download_url": "https://example.com/app.exe"},
                {"browser_download_url": "https://example.com/app.tar.gz"},
            ],
            "zipball_url": "https://fallback.com/zipball",
        }
        assert UpdateManager._select_download_url(data) == "https://fallback.com/zipball"


# ===========================================================================
# check_for_update  (mocked HTTP)
# ===========================================================================

class TestCheckForUpdate:

    def _mock_get(self, payload: dict, status_code: int = 200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            from requests import HTTPError
            resp.raise_for_status.side_effect = HTTPError(response=resp)
        return resp

    def test_update_available(self):
        mgr = make_manager(current_version="1.0.0")
        payload = fake_release_response(tag="v2.0.0")
        with patch("qpopcv.updater.requests.get", return_value=self._mock_get(payload)):
            info = mgr.check_for_update()
        assert info.available is True
        assert info.latest_version == "2.0.0"
        assert info.current_version == "1.0.0"
        assert info.download_url is not None

    def test_no_update_when_same_version(self):
        mgr = make_manager(current_version="2.0.0")
        payload = fake_release_response(tag="v2.0.0")
        with patch("qpopcv.updater.requests.get", return_value=self._mock_get(payload)):
            info = mgr.check_for_update()
        assert info.available is False

    def test_no_update_when_current_is_newer(self):
        mgr = make_manager(current_version="3.0.0")
        payload = fake_release_response(tag="v2.0.0")
        with patch("qpopcv.updater.requests.get", return_value=self._mock_get(payload)):
            info = mgr.check_for_update()
        assert info.available is False

    def test_network_error_returns_no_update(self):
        mgr = make_manager(current_version="1.0.0")
        import requests as req_lib
        with patch("qpopcv.updater.requests.get", side_effect=req_lib.ConnectionError("offline")):
            info = mgr.check_for_update()
        assert info.available is False
        assert info.download_url is None

    def test_timeout_returns_no_update(self):
        mgr = make_manager(current_version="1.0.0")
        import requests as req_lib
        with patch("qpopcv.updater.requests.get", side_effect=req_lib.Timeout()):
            info = mgr.check_for_update()
        assert info.available is False

    def test_bad_json_returns_no_update(self):
        mgr = make_manager(current_version="1.0.0")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = ValueError("bad json")
        with patch("qpopcv.updater.requests.get", return_value=resp):
            info = mgr.check_for_update()
        assert info.available is False


# ===========================================================================
# _find_source_root
# ===========================================================================

class TestFindSourceRoot:

    def test_single_top_level_dir_is_unwrapped(self, tmp_path):
        inner = tmp_path / "QPopCV-1.0.0"
        inner.mkdir()
        (inner / "main.py").write_text("pass")
        assert UpdateManager._find_source_root(tmp_path) == inner

    def test_files_at_root_returns_extract_dir(self, tmp_path):
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "requirements.txt").write_text("")
        assert UpdateManager._find_source_root(tmp_path) == tmp_path

    def test_macosx_dir_is_ignored(self, tmp_path):
        macos = tmp_path / "__MACOSX"
        macos.mkdir()
        inner = tmp_path / "QPopCV-1.0.0"
        inner.mkdir()
        (inner / "main.py").write_text("pass")
        # Only one real entry → should unwrap
        assert UpdateManager._find_source_root(tmp_path) == inner


# ===========================================================================
# _copy_tree
# ===========================================================================

class TestCopyTree:

    def test_copies_files_to_dest(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir(); dest.mkdir()
        (src / "main.py").write_text("print('hello')")
        mgr = make_manager(app_dir=dest)
        mgr._copy_tree(src, dest)
        assert (dest / "main.py").read_text() == "print('hello')"

    def test_skips_config_json(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir(); dest.mkdir()
        (src / "config.json").write_text('{"webhook_url": "new"}')
        (dest / "config.json").write_text('{"webhook_url": "old"}')
        mgr = make_manager(app_dir=dest)
        mgr._copy_tree(src, dest)
        # config.json must NOT be overwritten
        assert json.loads((dest / "config.json").read_text())["webhook_url"] == "old"

    def test_skips_hidden_files(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir(); dest.mkdir()
        (src / ".gitignore").write_text("*.pyc")
        mgr = make_manager(app_dir=dest)
        mgr._copy_tree(src, dest)
        assert not (dest / ".gitignore").exists()

    def test_skips_pycache(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir(); dest.mkdir()
        pycache = src / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_bytes(b"\x00")
        mgr = make_manager(app_dir=dest)
        mgr._copy_tree(src, dest)
        assert not (dest / "__pycache__").exists()

    def test_replaces_existing_directory(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir(); dest.mkdir()
        (src / "qpopcv").mkdir()
        (src / "qpopcv" / "new_module.py").write_text("new")
        (dest / "qpopcv").mkdir()
        (dest / "qpopcv" / "old_module.py").write_text("old")
        mgr = make_manager(app_dir=dest)
        mgr._copy_tree(src, dest)
        assert (dest / "qpopcv" / "new_module.py").exists()
        assert not (dest / "qpopcv" / "old_module.py").exists()
