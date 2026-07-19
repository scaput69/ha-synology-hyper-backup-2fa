"""Hyper Backup API using Home Assistant's authenticated DSM session."""

from __future__ import annotations

from typing import Any

from synology_dsm import SynologyDSM


class SynologyHyperBackupApi:
    """Make Hyper Backup calls through an existing SynologyDSM client."""

    TASK_API = "SYNO.Backup.Task"
    LOG_API = "SYNO.SDS.Backup.Client.Common.Log"

    def __init__(self, dsm: SynologyDSM) -> None:
        """Initialize the API adapter without creating another DSM session."""
        self._dsm = dsm

    async def _get(
        self, api: str, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an API using its minimum advertised version."""
        info = self._dsm.apis.get(api)

        kwargs: dict[str, Any] = {}
        if info is not None:
            kwargs["max_version"] = info["minVersion"]

        response = await self._dsm.get(api, method, params or {}, **kwargs)
        if not isinstance(response, dict):
            raise TypeError(f"Unexpected response type from {api}: {type(response)!r}")
        return response

    async def task_list(self) -> dict[str, Any]:
        """Return configured Hyper Backup tasks."""
        return await self._get(self.TASK_API, "list")

    async def task_status(self, task_id: int | str) -> dict[str, Any]:
        """Return live status for one task."""
        return await self._get(self.TASK_API, "status", {"task_id": task_id})

    async def task_result(self, task_id: int | str) -> dict[str, Any]:
        """Return the last result summary for one task."""
        return await self._get(
            self.TASK_API,
            "status",
            {
                "blOnline": "false",
                "additional": (
                    '["last_bkp_time","next_bkp_time","last_bkp_result",'
                    '"is_modified","last_bkp_progress"]'
                ),
                "task_id": task_id,
            },
        )

    async def logs(
        self,
        limit: int = 1000,
        offset: int = 0,
        filter_keyword: str = "",
    ) -> dict[str, Any]:
        """Return Hyper Backup logs."""
        return await self._get(
            self.LOG_API,
            "list",
            {
                "limit": limit,
                "offset": offset,
                "filter_keyword": filter_keyword,
                "filter_date_from": 0,
                "filter_date_to": 0,
            },
        )
