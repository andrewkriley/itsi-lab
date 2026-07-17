# ITSI POC SE Enablement Lab

Splunk IT Service Intelligence lab materials for the **Ruritania Application** POC scenario — revised guide, automation scripts (instructor use), and glass table assets.

## Contents

| File | Description |
|------|-------------|
| [`LAB_GUIDE.md`](LAB_GUIDE.md) | **Primary learner guide** (GUI-only, v2.1) |
| [`LAB_OUTCOMES.md`](LAB_OUTCOMES.md) | Validation checklist and audit notes |
| `configure_itsi_lab.py` | Automates Exercises 3–6 (instructor/optional) |
| `configure_glass_table.py` | Clones and wires the Ruritania glass table |
| `populate_glass_table_data.py` | KPI thresholds, backfill, error KPIs |
| `glass_table_*.json` | Glass table exports |
| `credentials.example.csv` | Credential file template |

The original Oct 2025 Word lab guide is included for reference.

## Credentials

**Do not commit real credentials.** Copy the template and add your Splunk Show instance details:

```bash
cp credentials.example.csv credentials.csv
# Edit credentials.csv with your Splunk Show URL, username, and password
```

Alternatively export environment variables:

```bash
export SPLUNK_HOST=your-instance.splunk.show
export SPLUNK_USER=Admin
export SPLUNK_PASSWORD='your-password'
```

Scripts also auto-detect a local `splunk-it-service-intelligence*.csv` if present (gitignored).

## Lab flow (learners)

Follow [`LAB_GUIDE.md`](LAB_GUIDE.md) in the Splunk Web UI. Estimated time: 2–3 hours.

## Automation (instructors)

```bash
python3 configure_itsi_lab.py
python3 configure_glass_table.py
python3 populate_glass_table_data.py
```

Allow 5–15 minutes after the last script for KPI backfill and episodes to populate.

## Requirements

- Python 3.9+
- Splunk Show instance with ITSI 4.21.x and Ruritania datagen
- REST API access on port **8089**

## Reference

- **Index:** `rur_apps`
- **Hosts:** `api-01`–`api-04`, `login-01`–`login-04`, `app-01`–`app-03`, `db-01`–`db-03`
- **Errors:** `status>=400 OR isnotnull(error)` (not `status=ERROR`)
