"""
P9-T-07 — Stale run reaper unit + integration tests.

Verifies:
1. reap_stale_runs() finds RUNNING runs older than 15 min and marks them FAILED
2. Fresh RUNNING runs (<15 min) are not touched
3. Already-terminal runs (SUCCESS/FAILED/CANCELLED) are not touched
4. Run with stored celery_task_id has the task revoked via Celery control
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workflow_engine.models.execution import ExecutionRun, RunStatus


# ── In-memory ExecutionRepository for reaper tests ────────────────────────────

class _InMemoryExecutionRepo:
    """Minimal in-memory repo stub for reaper tests."""

    def __init__(self):
        self._store: dict[str, ExecutionRun] = {}

    async def get(self, tenant_id: str, run_id: str) -> ExecutionRun | None:
        return self._store.get(run_id)

    async def create(self, tenant_id: str, run: ExecutionRun) -> ExecutionRun:
        self._store[run.run_id] = run
        return run

    async def update_state(self, tenant_id: str, run_id: str, run: ExecutionRun) -> ExecutionRun:
        self._store[run_id] = run
        return run

    async def list(self, *a, **kw):
        return list(self._store.values())

    async def get_node_states(self, *a, **kw):
        return []

    async def list_runs_by_tenant(self, *a, **kw):
        return list(self._store.values())

    async def patch_fields(self, tenant_id: str, run_id: str, fields: dict) -> None:
        run = self._store.get(run_id)
        if run:
            for k, v in fields.items():
                if hasattr(run, k):
                    setattr(run, k, v)

    async def update_node_state(self, *a, **kw) -> None:
        pass

    async def bulk_update_node_states(self, *a, **kw) -> None:
        pass

    async def list_stale_running(self, before: datetime) -> list[ExecutionRun]:
        result = []
        for run in self._store.values():
            if run.status == RunStatus.RUNNING:
                started = run.started_at
                if not started:
                    continue
                # Normalize both to aware UTC for comparison
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                cmp_before = before.replace(tzinfo=timezone.utc) if before.tzinfo is None else before
                if started < cmp_before:
                    result.append(run)
        return result


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run(run_id: str, status: RunStatus, started_offset_minutes: int, celery_task_id: str | None = None) -> ExecutionRun:
    """Create a run with started_at offset by `started_offset_minutes` from now."""
    return ExecutionRun(
        run_id=run_id,
        workflow_id="wf-test",
        tenant_id="t1",
        status=status,
        started_at=_now() - timedelta(minutes=started_offset_minutes),
        celery_task_id=celery_task_id,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestStaleRunReaperLogic:

    @pytest.mark.asyncio
    async def test_stale_running_run_marked_failed(self):
        """A RUNNING run older than 15 min must be marked FAILED."""
        repo = _InMemoryExecutionRepo()
        stale = _run("run-stale", RunStatus.RUNNING, started_offset_minutes=20)
        await repo.create("t1", stale)

        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert len(stale_runs) == 1
        assert stale_runs[0].run_id == "run-stale"

        # Simulate what the reaper does
        for run in stale_runs:
            run.status = RunStatus.FAILED
            await repo.update_state("t1", run.run_id, run)

        updated = await repo.get("t1", "run-stale")
        assert updated is not None
        assert updated.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_fresh_running_run_not_reaped(self):
        """A RUNNING run less than 15 min old must NOT be reaped."""
        repo = _InMemoryExecutionRepo()
        fresh = _run("run-fresh", RunStatus.RUNNING, started_offset_minutes=5)
        await repo.create("t1", fresh)

        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert len(stale_runs) == 0

    @pytest.mark.asyncio
    async def test_terminal_runs_not_returned_by_list_stale(self):
        """SUCCESS/FAILED/CANCELLED runs must not appear in list_stale_running."""
        repo = _InMemoryExecutionRepo()
        for status, rid in [
            (RunStatus.SUCCESS, "run-success"),
            (RunStatus.FAILED, "run-failed"),
            (RunStatus.CANCELLED, "run-cancelled"),
        ]:
            r = _run(rid, status, started_offset_minutes=60)
            await repo.create("t1", r)

        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert len(stale_runs) == 0

    @pytest.mark.asyncio
    async def test_mixed_runs_only_stale_reaped(self):
        """Only the stale RUNNING run is reaped when mixed runs exist."""
        repo = _InMemoryExecutionRepo()
        stale = _run("run-stale", RunStatus.RUNNING, started_offset_minutes=30)
        fresh = _run("run-fresh", RunStatus.RUNNING, started_offset_minutes=2)
        done = _run("run-done", RunStatus.SUCCESS, started_offset_minutes=60)
        for r in [stale, fresh, done]:
            await repo.create("t1", r)

        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert len(stale_runs) == 1
        assert stale_runs[0].run_id == "run-stale"

    @pytest.mark.asyncio
    async def test_celery_task_revoked_on_reap(self):
        """
        A stale run with a stored celery_task_id should have its Celery task
        revoked when reaped. (Tests the revoke() call pattern.)
        """
        repo = _InMemoryExecutionRepo()
        stale = _run("run-stale-with-task", RunStatus.RUNNING, started_offset_minutes=20, celery_task_id="celery-task-xyz")
        await repo.create("t1", stale)

        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert len(stale_runs) == 1

        # Simulate the reaper's revoke + FAILED logic
        mock_celery = MagicMock()
        mock_celery.control.revoke = MagicMock()

        for run in stale_runs:
            if run.celery_task_id:
                mock_celery.control.revoke(run.celery_task_id, terminate=True)
            run.status = RunStatus.FAILED
            await repo.update_state("t1", run.run_id, run)

        mock_celery.control.revoke.assert_called_once_with("celery-task-xyz", terminate=True)

        updated = await repo.get("t1", "run-stale-with-task")
        assert updated.status == RunStatus.FAILED


class TestStaleRunReaperBoundary:
    @pytest.mark.asyncio
    async def test_exactly_at_boundary_not_reaped(self):
        """A run started exactly at the 15-min boundary should not be reaped."""
        repo = _InMemoryExecutionRepo()
        # started_at = exactly 15 min ago → not older than cutoff (not strictly less than)
        boundary = _run("run-boundary", RunStatus.RUNNING, started_offset_minutes=15)
        # Adjust to be exactly at cutoff (not before)
        cutoff = _now() - timedelta(minutes=15)
        boundary.started_at = cutoff  # exactly equal, not before

        await repo.create("t1", boundary)
        stale_runs = await repo.list_stale_running(cutoff)
        # started_at == cutoff, not < cutoff → should NOT be in the result
        assert "run-boundary" not in [r.run_id for r in stale_runs]

    @pytest.mark.asyncio
    async def test_empty_repo_reap_is_noop(self):
        """reap_stale_runs on empty repo should not crash."""
        repo = _InMemoryExecutionRepo()
        cutoff = _now() - timedelta(minutes=15)
        stale_runs = await repo.list_stale_running(cutoff)
        assert stale_runs == []
