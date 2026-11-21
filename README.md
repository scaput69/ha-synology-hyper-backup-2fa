# Synology Hyper Backup for Home Assistant

**English** | [Français](README.fr.md)

This repository is a fork of
[`JurajNyiri/ha-synology-hyper-backup`](https://github.com/JurajNyiri/ha-synology-hyper-backup),
a Home Assistant custom integration for monitoring Synology Hyper Backup tasks
on a DSM NAS.

The original integration opened a second DSM session with the username and
password it read from Home Assistant. That approach did not reuse the MFA/2FA
validation of the official DSM integration, so it did not work with accounts
that use two-factor authentication.

This fork replaces that second connection with the already authenticated
session of the official Synology DSM integration and its MFA device token. It
also adds a reduced set of sensors, French and English translations, and
asynchronous handling of the Hyper Backup calls.

It complements the official
[Synology DSM](https://www.home-assistant.io/integrations/synology_dsm/)
integration and attaches its entities to the same device in Home Assistant.

## Features

The integration discovers Hyper Backup tasks automatically and creates eleven
sensors per task:

| Sensor | Description |
| --- | --- |
| Result | Last result: `done`, `failed`, `running`, etc. |
| Progress | Completion percentage while a backup runs |
| Last successful backup | Date of the last successful run |
| Next backup | Date of the next scheduled run |
| Integrity check | Date of the last successful integrity check |
| Source size | Size of the backed-up data in the latest version |
| Size on target | Space used by the backup on the destination |
| Last version growth | Change in size on the destination compared with the previous version |
| New files | Files added in the latest version |
| Modified files | Files modified in the latest version |
| Deleted files | Files deleted in the latest version |

The version statistics come from the same API as the Hyper Backup
"Statistics" window. They are only read again after a new run, not on every
refresh. The `version_time` and `previous_version_time` attributes show which
versions were compared.

The result sensor also has useful technical attributes: error message and
code, task ID, destination, transfer type and encryption status.

Progress shows `Unknown` while the task is idle. This is normal.

## Authentication and 2FA

This version does not open a second connection to the NAS and does not read
the DSM password again.

It reuses the authenticated session of the official Synology DSM integration
directly, including its device token. Two-factor authentication is therefore
supported through Home Assistant's native OTP flow.

When the session expires, the integration tries to reconnect with the token
managed by Synology DSM.

## Requirements

- Home Assistant 2025.8.3 or newer;
- before Home Assistant 2026.11: HACS 2.0.5 or newer for the HACS installation;
- a Synology NAS reachable from Home Assistant;
- Hyper Backup installed on the NAS;
- at least one configured Hyper Backup task;
- the official Synology DSM integration configured, loaded and working.

Set up Synology DSM first, including the OTP step if 2FA is enabled.

## Installation from the Marketplace or HACS

The integration is available in the default catalog. Since Home Assistant
2026.11, HACS is built into Home Assistant as the **Marketplace**.

### Home Assistant 2026.11 or newer

1. Open **Settings → Marketplace**.
2. Search for **Synology Hyper Backup**.
3. Select **Install**.
4. Follow the setup flow that opens directly.

No restart is needed for a first installation from the Marketplace.

### Older versions with HACS

1. Open **HACS**.
2. Search for **Synology Hyper Backup**.
3. Download the integration.
4. Restart Home Assistant.
5. Open **Settings → Devices & services**.
6. Click **Add integration**.
7. Search for **Synology Hyper Backup** and select the DSM instance that is
   already authenticated.

## Configuration

After the restart:

1. Open **Settings → Devices & services**.
2. Click **Add integration**.
3. Search for **Synology Hyper Backup**.
4. Select the Synology DSM instance that is already authenticated.

Each DSM entry can have only one Hyper Backup configuration.

## Manual installation

Copy the folder:

```text
custom_components/synology_hyper_backup
```

into the `custom_components` folder of your Home Assistant configuration, then
restart Home Assistant.

## Example with native cards

Entity IDs depend on the names of the NAS and the tasks. Replace the
`sensor.REPLACE_*` values with the IDs shown in Home Assistant.

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >-
      {% set entity = 'sensor.REPLACE_RESULT' %}
      {% set result = states(entity) %}
      ## Hyper Backup

      {% if result in ['done', 'success', 'ok'] %}
        🟢 **Backup succeeded**
      {% elif result in ['failed', 'error'] %}
        🔴 **Backup failed**
      {% elif result in ['running', 'backingup', 'preparing', 'starting'] %}
        🔵 **Backup in progress**
      {% else %}
        ⚪ **State: {{ result }}**
      {% endif %}

      {% set error = state_attr(entity, 'error') %}
      {% set code = state_attr(entity, 'error_code') %}
      {% if result in ['failed', 'error'] and (error or code) %}
        **Error:** {{ error or 'DSM error' }}{% if code %} ({{ code }}){% endif %}
      {% endif %}
  - type: entities
    show_header_toggle: false
    entities:
      - entity: sensor.REPLACE_LAST_SUCCESS
        name: Last success
        icon: mdi:clock-check-outline
      - entity: sensor.REPLACE_NEXT_BACKUP
        name: Next backup
        icon: mdi:clock-outline
      - entity: sensor.REPLACE_INTEGRITY_CHECK
        name: Integrity check
        icon: mdi:shield-check-outline
      - entity: sensor.REPLACE_PROGRESS
        name: Progress
        icon: mdi:progress-clock
```

This example only uses Home Assistant's native cards.

## Upgrading from versions 0.1 or 0.2

Older versions created an entity for almost every raw API field. Version 0.3
kept five essential sensors per task. Since version 0.4, six version statistics
sensors are added, for a total of eleven sensors per task.

After the upgrade, the old entities that were not kept become unavailable.
Check that no automation or card uses them, then delete them from
**Settings → Devices & services → Entities**.

## Troubleshooting

### The DSM integration does not appear in the list

Check that the official Synology DSM integration is loaded. Reload it if
needed before adding Synology Hyper Backup.

### All entities are unavailable

Reload both integrations first. If the problem persists, open
**Settings → System → Logs** and search for `synology_hyper_backup`.

### Progress is unknown

This is normal when no backup is running. A number is shown during a run when
DSM reports progress.

### A task has failed

Open the **Result** sensor and check its `error` and `error_code` attributes.
The messages come directly from the DSM API.

## Limitations

- The Hyper Backup APIs used are not officially documented and may change with
  DSM or the Hyper Backup package.
- Finding the integrity check currently relies on the English message produced
  by Hyper Backup.
- The integration polls the NAS locally every 60 seconds.
- The size on the destination does not include snapshots that the storage
  provider keeps on its side.
- The integration only monitors; it does not start, pause or delete any
  backup.

## Privacy and security

All communication stays local between Home Assistant and the NAS. The
integration does not send any credentials to an external service and does not
store any extra password or OTP code.

## Credits

The original code and concept come from
[JurajNyiri/ha-synology-hyper-backup](https://github.com/JurajNyiri/ha-synology-hyper-backup).

As its author notes, that integration was itself partly based on
[bbckr/ha-synology-tasks](https://github.com/bbckr/ha-synology-tasks), in the
version consulted on 28 December 2025. That project has a similar goal: monitoring
Synology tasks in Home Assistant.

The code lineage is therefore:

```text
bbckr/ha-synology-tasks
  └── JurajNyiri/ha-synology-hyper-backup
        └── scaput69/ha-synology-hyper-backup-2fa
```

This fork keeps the MIT license and the attribution to the original project.
The changes specific to this repository mainly concern MFA/2FA compatibility,
the use of the shared DSM session, the entity model and the documentation.

MIT License. This community project is not affiliated with Synology or Home
Assistant.
