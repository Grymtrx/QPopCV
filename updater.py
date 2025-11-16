from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence
import os
import re
import shutil
import sys
import tempfile
import zipfile

import requests


@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    download_url: Optional[str]
    release_url: Optional[str]
    release_name: str = ""


class UpdateManager:
    """Handles GitHub release update checks and installations."""

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
        self.app_dir = Path(app_dir or Path(__file__).resolve().parent)

    # --------- Public API ---------

    def check_for_updates(self) -> UpdateInfo:
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        response = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "QPopCV-Updater",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        latest_version = data.get("tag_name") or data.get("name") or ""
        download_url = self._select_download_url(data)
        release_url = data.get("html_url")
        release_name = data.get("name") or data.get("tag_name") or ""

        available = self._is_newer_version(latest_version, self.current_version)

        return UpdateInfo(
            available=available,
            current_version=self.current_version,
            latest_version=latest_version or "unknown",
            download_url=download_url,
            release_url=release_url,
            release_name=release_name,
        )

    def install_update(self, info: UpdateInfo) -> Path:
        if not info.download_url:
            raise RuntimeError("Release did not include a downloadable asset.")

        tmp_dir = Path(tempfile.mkdtemp(prefix="qpop_update_"))
        try:
            archive_path = self._download_file(info.download_url, tmp_dir)
            if zipfile.is_zipfile(archive_path):
                self._install_from_archive(archive_path, tmp_dir)
            else:
                target = self.app_dir / archive_path.name
                shutil.move(str(archive_path), target)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return self.app_dir

    def relaunch(self) -> None:
        python = sys.executable
        args = sys.argv
        os.execl(python, python, *args)

    # --------- Internal Helpers ---------

    @staticmethod
    def _normalize_version(version: str) -> Sequence[tuple[int, object]]:
        cleaned = version.strip()
        if not cleaned:
            return ()
        parts: list[tuple[int, object]] = []
        for token in re.split(r"[\.\-_]", cleaned):
            if not token:
                continue
            if token.isdigit():
                parts.append((0, int(token)))
            else:
                parts.append((1, token))
        return tuple(parts)

    def _is_newer_version(self, latest: str, current: str) -> bool:
        return self._normalize_version(latest) > self._normalize_version(current)

    @staticmethod
    def _select_download_url(data: dict) -> Optional[str]:
        assets = data.get("assets") or []
        for asset in assets:
            url = asset.get("browser_download_url")
            if url:
                return url
        return data.get("zipball_url")

    def _download_file(self, url: str, tmp_dir: Path) -> Path:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        filename = Path(url).name or "update.bin"
        dest = tmp_dir / filename
        with dest.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return dest

    def _install_from_archive(self, archive: Path, tmp_dir: Path) -> None:
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_dir)

        source_root = self._locate_source_root(extract_dir)
        self._copy_tree(source_root, self.app_dir)

    @staticmethod
    def _locate_source_root(extract_dir: Path) -> Path:
        entries = [p for p in extract_dir.iterdir() if not p.name.startswith("__MACOSX")]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extract_dir

    def _copy_tree(self, src: Path, dest: Path) -> None:
        for item in src.iterdir():
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

