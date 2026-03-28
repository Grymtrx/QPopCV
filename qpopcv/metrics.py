"""Persistent session metrics for QPopCV."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsStore:
    """Load, record, and compute session metrics from a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.sessions: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self.sessions = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.sessions = data.get("sessions", [])
        except Exception as exc:
            logger.warning("Failed to load metrics: %s", exc)
            self.sessions = []

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"sessions": self.sessions}, indent=2),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(self._path))

    def record_session(
        self,
        start: datetime,
        end: datetime,
        duration_seconds: int,
        detected: bool,
    ) -> Dict:
        session = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_seconds": duration_seconds,
            "detected": detected,
        }
        self.sessions.append(session)
        self._save()
        return session

    def compute(self, day: Optional[date] = None) -> Dict:
        filtered = self.sessions
        if day is not None:
            filtered = [
                s for s in self.sessions
                if datetime.fromisoformat(s["start"]).date() == day
            ]

        total = sum(s["duration_seconds"] for s in filtered)
        detected_sessions = [s for s in filtered if s["detected"]]
        effective = sum(s["duration_seconds"] for s in detected_sessions)
        pops = len(detected_sessions)
        avg = effective // pops if pops > 0 else 0
        longest = max((s["duration_seconds"] for s in filtered), default=0)

        return {
            "total_time_saved": total,
            "effective_time_saved": effective,
            "pops_detected": pops,
            "avg_queue_wait": avg,
            "longest_session": longest,
        }
