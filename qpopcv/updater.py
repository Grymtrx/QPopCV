from __future__ import annotations
import tkinter.messagebox as messagebox


from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence
import os
import subprocess
import re
import shutil
import sys
import tempfile
import zipfile
import subprocess

import requests


GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    download_url: Optional[str]
    release_url: Optional[str]
    release_name: str = ""


class UpdateManager:
    """
    Handles GitHub release update checks and installations.

    - check_for_update() -> UpdateInfo
    - install_update(info: UpdateInfo) -> None

    When running from a PyInstaller .exe, installation is done via an external
    update.bat script so the running executable and its DLLs can be replaced
    without hitting WinError 5 (access denied).
    """

    def __init__(
        self,
        repo_owner: str = "Grymtrx",
        repo_name: str = "QPopCV",
        current_version: str = "0.0.0",
        app_dir: Optional[Path] = None,
    ) -> None:
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = current_version

        if app_dir is not None:
            self.app_dir = Path(app_dir)
        else:
            # When frozen, app_dir is the folder containing the .exe
            if getattr(sys, "frozen", False):
                self.app_dir = Path(sys.executable).parent
            else:
                # When running from source, treat the project root as app_dir
                self.app_dir = Path(__file__).resolve().parent.parent

    # ----------------- Public API -----------------

    def check_for_update(self, timeout: float = 5.0) -> UpdateInfo:
        """
        Contact GitHub and determine whether a newer version is available.
        """
        current = self.current_version
        try:
            url = GITHUB_API.format(owner=self.repo_owner, repo=self.repo_name)
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

            latest_version = self._normalize_tag(data.get("tag_name") or "")
            download_url = self._select_download_url(data)
            html_url = data.get("html_url")

            if not latest_version or not download_url:
                # No usable release info
                return UpdateInfo(
                    available=False,
                    current_version=current,
                    latest_version=current,
                    download_url=None,
                    release_url=html_url,
                    release_name=data.get("name") or "",
                )

            is_newer = self._is_newer_version(latest_version, current)

            return UpdateInfo(
                available=is_newer,
                current_version=current,
                latest_version=latest_version,
                download_url=download_url,
                release_url=html_url,
                release_name=data.get("name") or "",
            )

        except Exception:
            # On any error (network, JSON, etc.), report "no update"
            return UpdateInfo(
                available=False,
                current_version=current,
                latest_version=current,
                download_url=None,
                release_url=None,
                release_name="",
            )

    def install_update(self, info: UpdateInfo, timeout: float = 30.0) -> None:
        """
        Download and install the specified update.

        - When running from source: directly copy the files over app_dir.
        - When running from a frozen .exe: spawn an external update.bat that
          performs the copy AFTER this process exits, then restarts the app.
        """
        if not info.available or not info.download_url:
            return

        # Create a persistent temp dir; the batch script will clean this up.
        tmp_dir = Path(tempfile.mkdtemp(prefix="qpopcv_update_"))
        zip_path = tmp_dir / "update.zip"
        extract_dir = tmp_dir / "extracted"

        # 1) Download the release zip
        self._download_file(info.download_url, zip_path, timeout=timeout)

        # 2) Extract it
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # 3) Determine the actual root of the extracted content
        source_root = self._find_source_root(extract_dir)

        # 4) Apply differently depending on frozen vs source
        if getattr(sys, "frozen", False):
            # Use an external updater that will:
            #  - wait for this exe to exit
            #  - copy files from source_root -> app_dir
            #  - restart the exe
            #  - delete the temp folder and itself
            self._run_external_updater(source_root, tmp_dir)
        else:
            # Running from source: just copy files over app_dir in-process
            self._copy_tree(source_root, self.app_dir)

    # ----------------- Internal helpers -----------------

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        # Turn "v1.2.3" or "release-1.2.3" into "1.2.3"
        if not tag:
            return ""
        m = re.search(r"(\d+(?:\.\d+)*)", tag)
        return m.group(1) if m else tag

    @staticmethod
    def _normalize_version(version: str) -> Sequence:
        # Normalize version string into a tuple for comparison
        parts: list[tuple[int, object]] = []
        for token in re.split(r"[^\w]+", version):
            if not token:
                continue
            if token.isdigit():
                parts.append((0, int(token)))
            else:
                parts.append((1, token))
        return tuple(parts)

    def _is_newer_version(self, latest: str, current: str) -> bool:
        try:
            return self._normalize_version(latest) > self._normalize_version(current)
        except Exception:
            # Fallback: simple string comparison if normalization fails
            return latest > current

    @staticmethod
    def _select_download_url(data: dict) -> Optional[str]:
        """
        Prefer a .zip asset if present. Otherwise fall back to zipball_url.
        """
        assets = data.get("assets") or []
        for asset in assets:
            url = asset.get("browser_download_url")
            if url and url.lower().endswith(".zip"):
                return url

        # Fallback: GitHub's auto-generated source zip
        zipball = data.get("zipball_url")
        return zipball or None

    @staticmethod
    def _download_file(url: str, dest: Path, timeout: float = 30.0) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

    @staticmethod
    def _find_source_root(extract_dir: Path) -> Path:
        """
        Handle both:
          - zips that contain files directly at the root
          - zips that contain a single top-level folder
        """
        entries = [p for p in extract_dir.iterdir() if not p.name.startswith("__MACOSX")]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extract_dir

    def _copy_tree(self, src: Path, dest: Path) -> None:
        """
        Copy src -> dest, skipping config.json and hidden files.
        Used only when running from source, where files are not locked.
        """
        for item in src.iterdir():
            # keep user config and hidden files in place
            if item.name == "config.json" or item.name.startswith("."):
                continue

            target = dest / item.name

            if item.is_dir():
                if item.name == "__pycache__":
                    continue
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    def _run_external_updater(self, source_root: Path, tmp_dir: Path) -> None:
        """
        Create and launch an update.bat script that:
          - waits for the current exe to exit
          - copies files from source_root -> app_dir
          - restarts the exe
          - deletes the temp dir and itself
        """
        exe_path = Path(sys.executable)
        exe_name = exe_path.name
        app_dir = self.app_dir

        bat_path = tmp_dir / "qpopcv_update.bat"

        # Paths must be absolute and quoted in the batch script
        src_str = str(source_root.resolve())
        dest_str = str(app_dir.resolve())
        exe_str = str(exe_path.resolve())

        script = f"""@echo off
setlocal ENABLEDELAYEDEXPANSION

set "SRC={src_str}"
set "DEST={dest_str}"
set "EXE={exe_str}"
set "TMPDIR={str(tmp_dir.resolve())}"

echo [QPopCV] Waiting for application to exit...

:waitloop
REM Check if the exe is still running
tasklist /FI "IMAGENAME eq {exe_name}" | find /I "{exe_name}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)

echo [QPopCV] Copying update files...
xcopy "%SRC%\\*" "%DEST%\\" /E /I /Y >nul

echo [QPopCV] Restarting application...
start "" "%EXE%"

REM Clean up extracted files and this script
rmdir /s /q "%TMPDIR%" 2>nul

del "%~f0" 2>nul

endlocal
"""

        bat_path.write_text(script, encoding="utf-8")

        # Launch the updater batch using the default shell handler.
        # This should open a visible cmd window and run the script.
        try:
            os.startfile(str(bat_path))
        except Exception as exc:
            # Last-resort debug message; if this fires, we know launch failed.
            try:
                messagebox.showerror(
                    "QPopCV Updater",
                    f"Failed to launch updater script:\n{exc}",
                )
            except Exception:
                pass

