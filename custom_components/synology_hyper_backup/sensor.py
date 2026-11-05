"""Curated sensors for Synology Hyper Backup tasks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONFIG_DEVICE_IDENTIFIERS,
    CONFIG_DEVICE_MANUFACTURER,
    CONFIG_DEVICE_MODEL,
    CONFIG_DEVICE_NAME,
    CONFIG_DEVICE_SW_VERSION,
    DOMAIN,
)
from .coordinator import SynologyTasksCoordinator


@dataclass(frozen=True, kw_only=True)
class HyperBackupSensorDescription(SensorEntityDescription):
    """Describe a curated Hyper Backup sensor."""

    source_key: str
    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _parse_dsm_datetime(value: Any) -> datetime | None:
    """Convert a DSM local date string to an aware datetime."""
    if not isinstance(value, str) or not value:
        return None

    for date_format in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            parsed = datetime.strptime(value, date_format)
            return parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        except ValueError:
            continue
    return None


def _result_value(task: dict[str, Any]) -> str | None:
    """Prefer a live running state, otherwise return the last result."""
    live_result = task.get("status_progress_result")
    if live_result and live_result not in ("none", "unknown"):
        return str(live_result)
    result = task.get("last_result_last_bkp_result")
    return str(result) if result not in (None, "") else None


def _result_attributes(task: dict[str, Any]) -> dict[str, Any]:
    """Expose technical details on the main result sensor."""
    attribute_keys = {
        "task_id": "task_id",
        "state": "status_state",
        "status": "status_status",
        "error": "last_result_last_bkp_error",
        "error_code": "last_result_last_bkp_error_code",
        "started_at": "last_result_last_bkp_time",
        "ended_at": "last_result_last_bkp_end_time",
        "target_id": "target_id",
        "target_type": "target_type",
        "transfer_type": "transfer_type",
        "encrypted": "data_enc",
    }
    return {
        attribute: task[source]
        for attribute, source in attribute_keys.items()
        if task.get(source) not in (None, "", "unknown")
    }


def _version_time(value: Any) -> datetime | None:
    """Convert a version end time (Unix timestamp) to an aware datetime."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return dt_util.utc_from_timestamp(value)


def _version_attributes(kind: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return the attributes describing the version a statistic belongs to."""

    def attributes(task: dict[str, Any]) -> dict[str, Any]:
        values = {
            "version_time": _version_time(task.get(f"statistics_{kind}_version_time")),
            "previous_version_time": _version_time(
                task.get(f"statistics_{kind}_previous_version_time")
            ),
        }
        return {key: value for key, value in values.items() if value is not None}

    return attributes


def _size_description(
    key: str, source_key: str, suggested_unit: str
) -> HyperBackupSensorDescription:
    """Describe a data size statistic reported by DSM in KiB."""
    kind = "source" if source_key.startswith("statistics_source") else "target"
    return HyperBackupSensorDescription(
        key=key,
        source_key=source_key,
        translation_key=key,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=suggested_unit,
        suggested_display_precision=1,
        value_fn=lambda task: _numeric_value(task.get(source_key)),
        attributes_fn=_version_attributes(kind),
    )


def _count_description(
    key: str, source_key: str, icon: str
) -> HyperBackupSensorDescription:
    """Describe a file count of the newest version."""
    return HyperBackupSensorDescription(
        key=key,
        source_key=source_key,
        translation_key=key,
        state_class=SensorStateClass.MEASUREMENT,
        icon=icon,
        value_fn=lambda task: _numeric_value(task.get(source_key)),
        attributes_fn=_version_attributes("source"),
    )


SENSOR_DESCRIPTIONS: tuple[HyperBackupSensorDescription, ...] = (
    HyperBackupSensorDescription(
        key="result",
        source_key="last_result_last_bkp_result",
        translation_key="result",
        icon="mdi:backup-restore",
        value_fn=_result_value,
        attributes_fn=_result_attributes,
    ),
    HyperBackupSensorDescription(
        key="progress",
        source_key="status_progress_progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:progress-clock",
        value_fn=lambda task: _numeric_value(task.get("status_progress_progress")),
    ),
    HyperBackupSensorDescription(
        key="last_success",
        source_key="last_result_last_bkp_success_time",
        translation_key="last_success",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda task: _parse_dsm_datetime(
            task.get("last_result_last_bkp_success_time")
        ),
    ),
    HyperBackupSensorDescription(
        key="next_backup",
        source_key="last_result_next_bkp_time",
        translation_key="next_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda task: _parse_dsm_datetime(
            task.get("last_result_next_bkp_time")
        ),
    ),
    HyperBackupSensorDescription(
        key="integrity_check",
        source_key="integrity_check_time",
        translation_key="integrity_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:shield-check-outline",
        value_fn=lambda task: _parse_dsm_datetime(task.get("integrity_check_time")),
        attributes_fn=lambda task: {
            key: value
            for key, value in {
                "event": task.get("integrity_check_event"),
                "level": task.get("integrity_check_level"),
                "user": task.get("integrity_check_user"),
            }.items()
            if value not in (None, "")
        },
    ),
    _size_description(
        "source_size", "statistics_source_size", UnitOfInformation.GIBIBYTES
    ),
    _size_description(
        "target_size", "statistics_target_size", UnitOfInformation.GIBIBYTES
    ),
    _size_description(
        "target_size_change",
        "statistics_target_size_change",
        UnitOfInformation.MEBIBYTES,
    ),
    _count_description("new_files", "statistics_new_count", "mdi:file-plus-outline"),
    _count_description(
        "modified_files", "statistics_modify_count", "mdi:file-edit-outline"
    ),
    _count_description(
        "deleted_files", "statistics_delete_count", "mdi:file-remove-outline"
    ),
)


def _numeric_value(value: Any) -> int | float | None:
    """Convert an API value to a Home Assistant numeric state."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    return None


class SynologyHyperBackupSensor(
    CoordinatorEntity[SynologyTasksCoordinator], SensorEntity
):
    """Representation of one curated Hyper Backup sensor."""

    entity_description: HyperBackupSensorDescription

    def __init__(
        self,
        task: dict[str, Any],
        description: HyperBackupSensorDescription,
        coordinator: SynologyTasksCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._task_id = task.get("task_id")
        task_name = str(task.get("name", self._task_id or "Unknown"))

        # Preserve the old useful entity IDs from versions 0.1/0.2.
        task_name_id = task_name.lower().replace(" ", "_")
        self._attr_unique_id = f"{task_name_id}_{description.source_key}"
        self._attr_translation_placeholders = {"task_name": task_name}
        self._attr_has_entity_name = True

        if identifiers_data := config_entry.data.get(CONFIG_DEVICE_IDENTIFIERS):
            identifiers = {tuple(identifier) for identifier in identifiers_data}
            self._attr_device_info = DeviceInfo(
                identifiers=identifiers,
                name=config_entry.data.get(CONFIG_DEVICE_NAME),
                manufacturer=config_entry.data.get(CONFIG_DEVICE_MANUFACTURER),
                model=config_entry.data.get(CONFIG_DEVICE_MODEL),
                sw_version=config_entry.data.get(CONFIG_DEVICE_SW_VERSION),
            )

    def _task(self) -> dict[str, Any] | None:
        """Return the current coordinator data for this task."""
        tasks = self.coordinator.data.get("task_list", [])
        return next(
            (
                task
                for task in tasks
                if isinstance(task, dict) and task.get("task_id") == self._task_id
            ),
            None,
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        if (task := self._task()) is None:
            return None
        return self.entity_description.value_fn(task)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return selected technical details."""
        if (task := self._task()) is None:
            return {}
        attributes_fn = self.entity_description.attributes_fn
        return attributes_fn(task) if attributes_fn else {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up curated sensors for all discovered tasks."""
    coordinator: SynologyTasksCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    existing_ids: set[str] = set()

    @callback
    def add_new_task_entities() -> None:
        entities: list[SynologyHyperBackupSensor] = []
        for task in coordinator.data.get("task_list", []):
            if not isinstance(task, dict) or task.get("task_id") is None:
                continue
            for description in SENSOR_DESCRIPTIONS:
                entity = SynologyHyperBackupSensor(
                    task, description, coordinator, entry
                )
                if entity.unique_id not in existing_ids:
                    existing_ids.add(entity.unique_id)
                    entities.append(entity)

        if entities:
            async_add_entities(entities)

    add_new_task_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_task_entities))
