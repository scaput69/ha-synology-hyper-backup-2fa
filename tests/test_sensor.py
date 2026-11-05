"""Tests for the statistic sensor descriptions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfInformation

from custom_components.synology_hyper_backup.sensor import SENSOR_DESCRIPTIONS
from custom_components.synology_hyper_backup.utils import summarize_statistics

from .const import STATISTICS_RESPONSE

COMPONENT = Path(__file__).parents[1] / "custom_components" / "synology_hyper_backup"
DESCRIPTIONS = {description.key: description for description in SENSOR_DESCRIPTIONS}


def _task() -> dict:
    summary = summarize_statistics(STATISTICS_RESPONSE["data"])
    return {"task_id": 1, **{f"statistics_{k}": v for k, v in summary.items()}}


def test_statistic_values() -> None:
    """Each new sensor reads its value from the merged statistics."""
    task = _task()

    values = {
        key: DESCRIPTIONS[key].value_fn(task)
        for key in (
            "source_size",
            "target_size",
            "target_size_change",
            "new_files",
            "modified_files",
            "deleted_files",
        )
    }

    assert values == {
        "source_size": 704374604,
        "target_size": 698808967,
        "target_size_change": 368510,
        "new_files": 11,
        "modified_files": 38,
        "deleted_files": 2,
    }


def test_sizes_are_kibibytes() -> None:
    """DSM reports KiB; Home Assistant converts to a readable unit."""
    for key, suggested in (
        ("source_size", UnitOfInformation.GIBIBYTES),
        ("target_size", UnitOfInformation.GIBIBYTES),
        ("target_size_change", UnitOfInformation.MEBIBYTES),
    ):
        description = DESCRIPTIONS[key]
        assert description.device_class is SensorDeviceClass.DATA_SIZE
        assert description.native_unit_of_measurement == UnitOfInformation.KIBIBYTES
        assert description.suggested_unit_of_measurement == suggested


def test_version_attributes() -> None:
    """The growth sensor tells which two versions were compared."""
    attributes = DESCRIPTIONS["target_size_change"].attributes_fn(_task())

    assert attributes == {
        "version_time": datetime(2026, 11, 3, 2, 40, 7, tzinfo=UTC),
        "previous_version_time": datetime(2026, 11, 2, 2, 40, tzinfo=UTC),
    }
    assert DESCRIPTIONS["new_files"].attributes_fn(_task())["version_time"] == (
        datetime(2026, 11, 3, 2, 39, 7, tzinfo=UTC)
    )


def test_missing_statistics_give_no_value() -> None:
    """Before the first fetch the sensors are unknown, not zero."""
    for key in ("source_size", "target_size_change", "deleted_files"):
        assert DESCRIPTIONS[key].value_fn({"task_id": 1}) is None
        assert DESCRIPTIONS[key].attributes_fn({"task_id": 1}) == {}


def test_unique_ids_and_translations() -> None:
    """Every sensor has its own unique id suffix and a name in each language."""
    source_keys = [description.source_key for description in SENSOR_DESCRIPTIONS]
    assert len(source_keys) == len(set(source_keys))

    for path in (COMPONENT / "strings.json", *COMPONENT.glob("translations/*.json")):
        names = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
        for description in SENSOR_DESCRIPTIONS:
            assert "{task_name}" in names[description.translation_key]["name"], path
