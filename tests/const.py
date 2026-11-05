"""Shared test data, shaped like real DSM 7.3 responses."""

# SYNO.SDS.Backup.Client.Common.Statistic get, three daily versions.
STATISTICS_RESPONSE = {
    "success": True,
    "data": {
        "source_list": [
            {
                "end_time": 1793500615,
                "new_count": 29,
                "modify_count": 86,
                "delete_count": 10,
                "source_size": 703857632,
            },
            {
                "end_time": 1793587156,
                "new_count": 16,
                "modify_count": 40,
                "delete_count": 2,
                "source_size": 704377612,
            },
            {
                "end_time": 1793673547,
                "new_count": 11,
                "modify_count": 38,
                "delete_count": 2,
                "source_size": 704374604,
            },
        ],
        "source_previous_next_list": [
            {
                "end_time": 0,
                "new_count": 0,
                "modify_count": 0,
                "delete_count": 0,
                "source_size": 0,
            },
            {
                "end_time": 0,
                "new_count": 0,
                "modify_count": 0,
                "delete_count": 0,
                "source_size": 0,
            },
        ],
        "target_list": [
            {"end_time": 1793500656, "target_size": 697543800},
            {"end_time": 1793587200, "target_size": 698440457},
            {"end_time": 1793673607, "target_size": 698808967},
        ],
        "target_previous_next_list": [
            {"end_time": 0, "target_size": 0},
            {"end_time": 0, "target_size": 0},
        ],
    },
}
