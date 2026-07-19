"""Data update coordinator for Synology Tasks."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.synology_dsm.common import SynoApi
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMNotLoggedInException,
)

from .api import SynologyHyperBackupApi
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .utils import search_logs

_LOGGER = logging.getLogger(__name__)


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

    @staticmethod
    def _merge_with_prefix(task: dict, payload: dict | None, prefix: str) -> None:
        """Merge payload data onto task under the given prefix."""
        if not isinstance(payload, dict):
            return
        data = payload.get("data", payload)
        if isinstance(data, dict):
            task.update({f"{prefix}{key}": value for key, value in data.items()})

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
