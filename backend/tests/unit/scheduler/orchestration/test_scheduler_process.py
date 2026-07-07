# Copyright (c) 2016-2026 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scheduler.orchestration.scheduler_process import SchedulerProcess


async def _sleep_forever():
    await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_stop_process_cleans_up_everything():
    """stop_process must cancel the run task AND the engine task, and shut
    down the night monitor — not just self.task."""
    process = SchedulerProcess("test", MagicMock())

    run_task = asyncio.create_task(_sleep_forever())
    engine_task = asyncio.create_task(_sleep_forever())
    process.task = run_task
    process._engine_task = engine_task
    process.night_monitor = MagicMock()
    process.night_monitor.shutdown = AsyncMock()
    process.running_event.set()

    await process.stop_process()

    assert run_task.done(), "run task still alive after stop_process"
    assert engine_task.done(), "engine task leaked by stop_process"
    process.night_monitor.shutdown.assert_awaited_once()
    assert not process.running_event.is_set()


@pytest.mark.asyncio
async def test_stop_process_before_start_does_not_crash():
    """Stopping a process that never started is a no-op, not a crash."""
    process = SchedulerProcess("test", MagicMock())
    await process.stop_process()
    assert not process.running_event.is_set()


@pytest.mark.asyncio
async def test_night_monitor_shutdown_cancels_night_tracker():
    """NightMonitor.shutdown must also stop the night tracker task, which has
    no shutdown_event of its own."""
    from scheduler.night_monitor.night_monitor import NightMonitor

    with patch('scheduler.night_monitor.night_monitor.gpp'), \
         patch('scheduler.night_monitor.night_monitor.EventListener'), \
         patch('scheduler.night_monitor.night_monitor.EventConsumer'), \
         patch('scheduler.night_monitor.night_monitor.NightTracker'):
        monitor = NightMonitor(MagicMock(), frozenset(), MagicMock())

    monitor._listener_task = asyncio.create_task(_sleep_forever())
    monitor._consumer_task = asyncio.create_task(_sleep_forever())
    monitor._night_tracker_task = asyncio.create_task(_sleep_forever())

    await monitor.shutdown(drain_queue=False)

    assert monitor._night_tracker_task.done(), "night tracker task leaked by shutdown"
    assert monitor._listener_task.done()
    assert monitor._consumer_task.done()
