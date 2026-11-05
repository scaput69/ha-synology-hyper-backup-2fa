"""Data update coordinator for Synology Tasks."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.synology_dsm.common import SynoApi
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMNotLoggedInException,
)

from .api import SynologyHyperBackupApi
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STATISTICS_RETRY_PERIOD,
    STATISTICS_WINDOW,
)
from .utils import search_logs, summarize_statistics

_LOGGER = logging.getLogger(__name__)


def _parse_dsm_timestamp(value: Any) -> int | None:
    """Convert a DSM local date string to a Unix timestamp."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None
    return int(parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE).timestamp())


class SynologyTasksCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Synology task data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        dsm_api: SynoApi,
        synology_backup: SynologyHyperBackupApi,
    ) -> None:
        """Initialize the data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.dsm_api = dsm_api
        self.synology_backup = synology_backup
        # Statistics only change when a backup finishes, so they are cached per
        # task and keyed on the last backup run instead of polled every minute.
        self._statistics: dict[Any, tuple[tuple, dict[str, Any]]] = {}

    @staticmethod
    def _merge_with_prefix(task: dict, payload: dict | None, prefix: str) -> None:
        """Merge payload data onto task under the given prefix."""
        if not isinstance(payload, dict):
            return
        data = payload.get("data", payload)
        if isinstance(data, dict):
            task.update({f"{prefix}{key}": value for key, value in data.items()})

    async def _task_statistics(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return version statistics, fetched again only after a new backup run."""
        task_id = task["task_id"]
        run_key = (
            task.get("last_result_last_bkp_time"),
            task.get("last_result_last_bkp_end_time"),
            task.get("last_result_last_bkp_result"),
        )
        cached = self._statistics.get(task_id)
        if cached is not None and cached[0] == run_key:
            return cached[1]

        now = int(dt_util.utcnow().timestamp())
        try:
            response = await self.synology_backup.statistics(
                task_id, now - STATISTICS_WINDOW, now
            )
        except SynologyDSMNotLoggedInException:
            raise
        except SynologyDSMException as err:
            _LOGGER.debug("Statistics for task %s unavailable: %s", task_id, err)
            return cached[1] if cached is not None else {}

        data = response.get("data")
        summary = summarize_statistics(data) if isinstance(data, dict) else {}

        # DSM may record the new version a moment after the run is reported as
        # done; keep asking for a while until it shows up.
        started = _parse_dsm_timestamp(run_key[0])
        ended = _parse_dsm_timestamp(run_key[1])
        if (
            run_key[2] == "done"
            and started is not None
            and summary.get("target_version_time", 0) < started
            and ended is not None
            and now - ended < STATISTICS_RETRY_PERIOD
        ):
            return cached[1] if cached is not None else summary

        self._statistics[task_id] = (run_key, summary)
        return summary

    async def _fetch_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        tasks_list, hb_logs_resp = await asyncio.gather(
            self.synology_backup.task_list(),
            self.synology_backup.logs(
                filter_keyword=(
                    "Backup integrity check is finished. No error was found."
                )
            ),
        )
        data = tasks_list.get("data")
        if not isinstance(data, dict):
            raise UpdateFailed("Unexpected task data returned by Synology")

        log_data = hb_logs_resp.get("data", {})
        log_list = log_data.get("log_list", []) if isinstance(log_data, dict) else []

        tasks = data.get("task_list", [])
        if not isinstance(tasks, list):
            raise UpdateFailed("Unexpected task list returned by Synology")

        request_limit = asyncio.Semaphore(4)

        async def enrich_task(task: dict[str, Any]) -> None:
            task_id = task.get("task_id")
            if task_id is None:
                return
            latest_ic = search_logs(log_list, str(task.get("name", "")))
            async with request_limit:
                last_result, status_response = await asyncio.gather(
                    self.synology_backup.task_result(task_id),
                    self.synology_backup.task_status(task_id),
                )
            status = status_response.get("data", {})
            status_progress = (
                status.get("progress") if isinstance(status, dict) else None
            )
            self._merge_with_prefix(task, last_result, "last_result_")
            self._merge_with_prefix(task, status, "status_")
            self._merge_with_prefix(task, status_progress, "status_progress_")
            async with request_limit:
                statistics = await self._task_statistics(task)
            self._merge_with_prefix(task, statistics, "statistics_")

            if latest_ic:
                self._merge_with_prefix(task, latest_ic, "integrity_check_")

        await asyncio.gather(
            *(enrich_task(task) for task in tasks if isinstance(task, dict))
        )
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data and renew the shared DSM session once if it expired."""
        for attempt in range(2):
            try:
                return await self._fetch_data()
            except SynologyDSMNotLoggedInException:
                if attempt == 0:
                    _LOGGER.debug("DSM session expired; renewing the shared session")
                    try:
                        await self.dsm_api.async_login()
                    except SynologyDSMException as err:
                        raise UpdateFailed(
                            "The shared DSM session could not be renewed; "
                            "reconfigure the Synology DSM integration"
                        ) from err
                    continue
                raise UpdateFailed("DSM session could not be renewed")
            except SynologyDSMException as err:
                raise UpdateFailed(f"Error communicating with DSM: {err}") from err

        raise UpdateFailed("Unknown error communicating with DSM")
