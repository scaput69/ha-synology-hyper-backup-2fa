"""Tests for fetching and caching the version statistics."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from synology_dsm.exceptions import SynologyDSMAPIErrorException

from custom_components.synology_hyper_backup.const import DOMAIN
from custom_components.synology_hyper_backup.coordinator import (
    SynologyTasksCoordinator,
)

from .const import STATISTICS_RESPONSE

# The newest version in STATISTICS_RESPONSE ends at 03:40:07 local time.
LAST_RUN = {
    "last_bkp_time": "2026/11/03 03:30:01",
    "last_bkp_end_time": "2026/11/03 03:40:28",
    "last_bkp_result": "done",
}


def _api(last_run: dict[str, Any]) -> MagicMock:
    """Return a Hyper Backup API mock for one task."""
    api = MagicMock()
    api.task_list = AsyncMock(
        side_effect=lambda: {
            "data": {"task_list": [{"task_id": 1, "name": "Offsite"}], "total": 1}
        }
    )
    api.logs = AsyncMock(return_value={"data": {"log_list": []}})
    api.task_result = AsyncMock(side_effect=lambda _: {"data": dict(last_run)})
    api.task_status = AsyncMock(return_value={"data": {"state": "backupable"}})
    api.statistics = AsyncMock(return_value=STATISTICS_RESPONSE)
    return api


@pytest.fixture
async def amsterdam(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run in the NAS time zone, shortly after the last backup."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-03T08:00:00+01:00")


def _coordinator(hass: HomeAssistant, api: MagicMock) -> SynologyTasksCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return SynologyTasksCoordinator(hass, entry, MagicMock(), api)


def _task(data: dict[str, Any]) -> dict[str, Any]:
    return data["task_list"][0]


@pytest.mark.usefixtures("amsterdam")
async def test_statistics_are_merged_and_cached(hass: HomeAssistant) -> None:
    """Statistics are fetched once per backup run, not on every poll."""
    last_run = dict(LAST_RUN)
    api = _api(last_run)
    coordinator = _coordinator(hass, api)

    task = _task(await coordinator._async_update_data())
    assert task["statistics_target_size"] == 698808967
    assert task["statistics_target_size_change"] == 368510
    assert task["statistics_new_count"] == 11
    task_id, start, end = api.statistics.await_args.args
    assert task_id == 1
    assert end - start == 35 * 24 * 60 * 60

    task = _task(await coordinator._async_update_data())
    assert task["statistics_target_size"] == 698808967
    assert api.statistics.await_count == 1

    last_run["last_bkp_time"] = "2026/11/04 03:30:01"
    last_run["last_bkp_end_time"] = "2026/11/04 03:39:00"
    await coordinator._async_update_data()
    assert api.statistics.await_count == 2


@pytest.mark.usefixtures("amsterdam")
async def test_waits_for_new_version_after_run(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A run without its version yet is asked again for a while, then cached."""
    last_run = {
        "last_bkp_time": "2026/11/04 03:30:01",
        "last_bkp_end_time": "2026/11/04 03:39:00",
        "last_bkp_result": "done",
    }
    api = _api(last_run)
    coordinator = _coordinator(hass, api)

    freezer.move_to("2026-11-04T03:40:00+01:00")
    task = _task(await coordinator._async_update_data())
    assert task["statistics_target_size"] == 698808967
    await coordinator._async_update_data()
    assert api.statistics.await_count == 2

    freezer.move_to("2026-11-04T04:00:00+01:00")
    await coordinator._async_update_data()
    await coordinator._async_update_data()
    assert api.statistics.await_count == 3


@pytest.mark.usefixtures("amsterdam")
async def test_failed_run_is_not_retried(hass: HomeAssistant) -> None:
    """A failed run creates no version, so there is nothing to wait for."""
    last_run = dict(LAST_RUN, last_bkp_time="2026/11/04 03:30:01")
    last_run["last_bkp_result"] = "failed"
    api = _api(last_run)
    coordinator = _coordinator(hass, api)

    await coordinator._async_update_data()
    await coordinator._async_update_data()
    assert api.statistics.await_count == 1


@pytest.mark.usefixtures("amsterdam")
async def test_statistics_error_keeps_other_data(hass: HomeAssistant) -> None:
    """Without the statistics API the existing sensors keep working."""
    api = _api(dict(LAST_RUN))
    api.statistics.side_effect = SynologyDSMAPIErrorException(
        "SYNO.SDS.Backup.Client.Common.Statistic", 102, None
    )
    coordinator = _coordinator(hass, api)

    task = _task(await coordinator._async_update_data())
    assert task["last_result_last_bkp_result"] == "done"
    assert not any(key.startswith("statistics_") for key in task)
