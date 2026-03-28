"""Tests for qpopcv/metrics.py — session persistence and metric computation."""
import json
import pytest
from pathlib import Path
from datetime import datetime, date

from qpopcv.metrics import MetricsStore


@pytest.fixture
def store(tmp_path):
    return MetricsStore(tmp_path / "metrics.json")


class TestMetricsStore:

    def test_load_empty_file(self, store):
        """No file yet → empty sessions list."""
        assert store.sessions == []

    def test_record_session(self, store):
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        assert len(store.sessions) == 1
        s = store.sessions[0]
        assert s["duration_seconds"] == 758
        assert s["detected"] is True

    def test_persists_to_disk(self, store):
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        store2 = MetricsStore(store._path)
        assert len(store2.sessions) == 1

    def test_multiple_sessions(self, store):
        for i in range(3):
            store.record_session(
                start=datetime(2026, 3, 28, 14, i * 20, 0),
                end=datetime(2026, 3, 28, 14, i * 20 + 12, 0),
                duration_seconds=720,
                detected=(i % 2 == 0),
            )
        assert len(store.sessions) == 3


class TestMetricsCompute:

    def _store_with_data(self, tmp_path):
        store = MetricsStore(tmp_path / "metrics.json")
        store.record_session(
            start=datetime(2026, 3, 28, 14, 0, 0),
            end=datetime(2026, 3, 28, 14, 12, 38),
            duration_seconds=758,
            detected=True,
        )
        store.record_session(
            start=datetime(2026, 3, 28, 15, 0, 0),
            end=datetime(2026, 3, 28, 15, 45, 0),
            duration_seconds=2700,
            detected=False,
        )
        store.record_session(
            start=datetime(2026, 3, 27, 10, 0, 0),
            end=datetime(2026, 3, 27, 10, 20, 0),
            duration_seconds=1200,
            detected=True,
        )
        return store

    def test_compute_all_time(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute()
        assert m["total_time_saved"] == 758 + 2700 + 1200
        assert m["effective_time_saved"] == 758 + 1200
        assert m["pops_detected"] == 2
        assert m["avg_queue_wait"] == (758 + 1200) // 2
        assert m["longest_session"] == 2700

    def test_compute_today(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute(day=date(2026, 3, 28))
        assert m["total_time_saved"] == 758 + 2700
        assert m["effective_time_saved"] == 758
        assert m["pops_detected"] == 1
        assert m["avg_queue_wait"] == 758
        assert m["longest_session"] == 2700

    def test_compute_empty(self, tmp_path):
        store = MetricsStore(tmp_path / "metrics.json")
        m = store.compute()
        assert m["total_time_saved"] == 0
        assert m["effective_time_saved"] == 0
        assert m["pops_detected"] == 0
        assert m["avg_queue_wait"] == 0
        assert m["longest_session"] == 0

    def test_compute_no_pops_day(self, tmp_path):
        store = self._store_with_data(tmp_path)
        m = store.compute(day=date(2026, 3, 26))
        assert m["pops_detected"] == 0
        assert m["avg_queue_wait"] == 0
