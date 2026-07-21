# ITSI POC SE Enablement Lab

Splunk IT Service Intelligence lab materials for the **Ruritania Application** POC scenario.

The lab is delivered as a **GUI-only, hands-on guide** — learners complete every step in the Splunk Web UI. No scripts, REST API, or local files are required.

## Start here

Follow **[`LAB_GUIDE.md`](LAB_GUIDE.md)** — the primary learner guide (**GUI-only, v2.9**). Everything is done in the Splunk Web UI. Estimated time: **2–3 hours**.

## Contents

| File | Description |
|------|-------------|
| [`LAB_GUIDE.md`](LAB_GUIDE.md) | **Primary learner guide** (GUI-only, v2.9) |
| `ITSI POC ... Oct 2025.docx` | Original Oct 2025 Word lab guide, kept for reference |

## Reference

- **Index:** `rur_apps`
- **Hosts (14):** `api-01`–`api-04`, `login-01`–`login-04`, `app-01`–`app-03`, `db-01`–`db-03`
- **Errors:** `status>=400 OR isnotnull(error)` (not `status=ERROR`)
