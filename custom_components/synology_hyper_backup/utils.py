from datetime import datetime

LOG_TIME_FORMAT = "%Y/%m/%d %H:%M:%S"


def search_logs(log_list: list[dict], task_name: str) -> dict | None:
    """
    Return the most recent log entry for the given task name.
    Looks for events like "[Network][<task>] Backup integrity check is finished..."
    """
    matches = []
    needle = f"][{task_name}]"
    for entry in log_list:
        event = entry.get("event", "")
        if needle not in event:
            continue
        try:
            when = datetime.strptime(entry["time"], LOG_TIME_FORMAT)
        except Exception:
            continue
        matches.append((when, entry))
    if not matches:
        return None
    matches.sort(key=lambda tup: tup[0], reverse=True)
    return matches[0][1]


def _versions(data: dict, key: str) -> list[dict]:
    """Return the real versions under key, oldest first."""
    entries = data.get(key)
    if not isinstance(entries, list):
        return []
    versions = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("end_time"), (int, float))
        and entry["end_time"] > 0
    ]
    return sorted(versions, key=lambda entry: entry["end_time"])


def summarize_statistics(data: dict) -> dict:
    """
    Summarize a SYNO.SDS.Backup.Client.Common.Statistic response.

    Returns the file counts and sizes (KiB) of the newest version, and the
    change in size against the version before it. The previous version may be
    outside the requested window; DSM then returns it in the
    *_previous_next_list keys.
    """
    summary: dict = {}
    for kind, size_key in (("source", "source_size"), ("target", "target_size")):
        versions = _versions(data, f"{kind}_list")
        if not versions:
            continue
        latest = versions[-1]
        previous = versions[-2] if len(versions) > 1 else None
        if previous is None:
            earlier = [
                entry
                for entry in _versions(data, f"{kind}_previous_next_list")
                if entry["end_time"] < latest["end_time"]
            ]
            previous = earlier[-1] if earlier else None

        size = latest.get(size_key)
        summary[f"{kind}_size"] = size
        summary[f"{kind}_version_time"] = latest["end_time"]
        if (
            previous is not None
            and isinstance(size, (int, float))
            and isinstance(previous.get(size_key), (int, float))
        ):
            summary[f"{kind}_size_change"] = size - previous[size_key]
            summary[f"{kind}_previous_version_time"] = previous["end_time"]
        if kind == "source":
            for count_key in ("new_count", "modify_count", "delete_count"):
                summary[count_key] = latest.get(count_key)
    return summary
