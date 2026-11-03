"""Tests for the pure helpers."""

from custom_components.synology_hyper_backup.utils import summarize_statistics

from .const import STATISTICS_RESPONSE


def test_summarize_uses_newest_version_and_growth() -> None:
    """The newest version gives the counts, the one before it the change."""
    summary = summarize_statistics(STATISTICS_RESPONSE["data"])

    assert summary == {
        "source_size": 704374604,
        "source_version_time": 1793673547,
        "source_size_change": -3008,
        "source_previous_version_time": 1793587156,
        "new_count": 11,
        "modify_count": 38,
        "delete_count": 2,
        "target_size": 698808967,
        "target_version_time": 1793673607,
        "target_size_change": 368510,
        "target_previous_version_time": 1793587200,
    }


def test_summarize_sorts_versions() -> None:
    """DSM order is not relied on."""
    data = {
        "target_list": [
            {"end_time": 300, "target_size": 30},
            {"end_time": 100, "target_size": 10},
            {"end_time": 200, "target_size": 25},
        ]
    }

    summary = summarize_statistics(data)

    assert summary["target_size"] == 30
    assert summary["target_size_change"] == 5
    assert summary["target_previous_version_time"] == 200


def test_summarize_falls_back_to_version_before_window() -> None:
    """With one version in the window, the previous one comes from DSM's extra list."""
    data = {
        "target_list": [{"end_time": 500, "target_size": 120}],
        "target_previous_next_list": [
            {"end_time": 400, "target_size": 100},
            {"end_time": 0, "target_size": 0},
        ],
    }

    summary = summarize_statistics(data)

    assert summary["target_size_change"] == 20
    assert summary["target_previous_version_time"] == 400


def test_summarize_first_version_has_no_change() -> None:
    """The first backup has nothing to compare with."""
    data = {
        "source_list": [
            {
                "end_time": 500,
                "source_size": 80,
                "new_count": 7,
                "modify_count": 0,
                "delete_count": 0,
            }
        ],
        "source_previous_next_list": [
            {"end_time": 0, "source_size": 0},
            {"end_time": 0, "source_size": 0},
        ],
        "target_list": [],
    }

    summary = summarize_statistics(data)

    assert summary == {
        "source_size": 80,
        "source_version_time": 500,
        "new_count": 7,
        "modify_count": 0,
        "delete_count": 0,
    }


def test_summarize_ignores_malformed_data() -> None:
    """Unexpected shapes give an empty summary instead of an error."""
    assert summarize_statistics({}) == {}
    assert summarize_statistics({"target_list": "nope"}) == {}
    assert summarize_statistics({"target_list": [None, {"target_size": 5}]}) == {}
    assert summarize_statistics(
        {"target_list": [{"end_time": 2, "target_size": None}, {"end_time": 1}]}
    ) == {"target_size": None, "target_version_time": 2}
