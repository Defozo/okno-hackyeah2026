import asyncio
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path
import time

import pytest
from fastapi import HTTPException
from api import worker


def example():
    return json.loads(Path('data/synthetic/single-parent.json').read_text(encoding='utf-8'))


def test_total_budget_returns_unknown_and_reaps_process(monkeypatch):
    monkeypatch.setattr(worker, 'settings', replace(worker.settings, solver_budget=.01))
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    result = asyncio.run(worker.run_solver(example()))
    assert result['status'] == 'UNKNOWN'
    assert time.monotonic() - started < 2
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_busy_pool_rejects_another_job_without_queueing(monkeypatch):
    async def run():
        slots = asyncio.Semaphore(1)
        monkeypatch.setattr(worker, '_slots', slots)
        async with slots:
            with pytest.raises(HTTPException) as rejected:
                await worker.run_solver(example())
            assert rejected.value.status_code == 429
    asyncio.run(run())
