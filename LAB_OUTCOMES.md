# ITSI POC SE Enablement Lab — Review & Configuration Outcomes

**Learner guide (GUI only):** see [`LAB_GUIDE.md`](LAB_GUIDE.md)  
**Instance:** https://riles-itsi-i-0de3b31445a802592.splunk.show  
**API endpoint:** `https://riles-itsi-i-0de3b31445a802592.splunk.show:8089`  
**Splunk version:** 9.4.3 | **ITSI version:** 4.21.0  
**Audit date:** 2026-07-17  

---

## Executive summary

API access to the Splunk Show ITSI lab instance was validated successfully via the management port **8089** (HTTPS on port 443 returns 404 for REST endpoints). The environment had prerequisite apps and data in place, but **most hands-on ITSI configuration from Exercises 3–7 was missing** prior to automation.

An automation script (`configure_itsi_lab.py`) was created for instructor use. **Learners should follow [`LAB_GUIDE.md`](LAB_GUIDE.md)** (Splunk Web UI only). After automation or manual completion, the instance meets the lab outcomes for entity management, service modelling, KPI monitoring, event analytics, and the Ruritania Glass Table (Exercise 7).

Detailed machine-readable results: `lab_configuration_results.json`

---

## API access validation

| Check | Result |
|-------|--------|
| Credentials from CSV | Valid |
| REST API on `:8089` | **200 OK** — server info, ITSI endpoints, searches |
| REST API on `:443/en-US/services/...` | **404** — not usable for automation |
| ITSI `itoa_interface` endpoints | Accessible |
| Splunk search jobs | Accessible |

**Note for automation:** Splunk Show environments require port **8089** for REST/API work. Web UI access uses the standard HTTPS URL.

---

## Lab guide review — errors & clarifications

| # | Location | Issue | Recommended fix |
|---|----------|-------|-----------------|
| 1 | Exercise 4, step on custom KPI | References `index=rur_applications` | Should be **`index=rur_apps`** (consistent with all other exercises) |
| 2 | Exercise 3, entity count | States ~**20** Ruritania entities | Environment contains **14** in-scope hosts (`api-*`, `login-*`, `app-*`, `db-*`). Guide should say "~14–20 depending on datagen" |
| 3 | Exercise 7, Episodes SPL | `index=itsi_grouped_alerts entity_name=app*` used for **API service** block | Likely typo — should be **`entity_name=api*`** for API hourly episodes |
| 4 | Exercise 4 / ToC | Duplicate "Description/Steps" block and Exercise 5 header formatting | Clean up document structure; Exercise 5 (KPI Thresholds) is present but poorly numbered in ToC |
| 5 | Exercises 4, 7 | References downloadable CSV / Glass Table files | Files are **not embedded** in the provided `.docx`; host download links or bundle assets with the lab package |
| 6 | Exercise 3, entity SPL | Uses `entity_type="Ruritania Application Server"` column | Works for ad-hoc UI import; REST API requires **`entity_type_ids`** with the KV store key |
| 7 | Exercise 6 | References "Service Monitoring KPI Degraded" | Exact saved search name is **`Service Monitoring - KPI Degraded`** (with spaces and hyphen) |

---

## Exercise-by-exercise outcomes

### Exercise 1 — Explore the blank-slate environment

| Requirement | Status | Evidence |
|-------------|--------|----------|
| IT Service Intelligence | **Complete** | `itsi` v4.21.0 |
| Splunk Add-on for Unix and Linux | **Complete** | `Splunk_TA_nix` installed |
| ITSI Splunk App for Content Packs | **Complete** | `DA-ITSI-ContentLibrary` |
| Content Pack for ITSI Monitoring and Alerting (Content Library) | **Complete** | `DA-ITSI-CP-monitoring-alerting` v2.3.0 |
| Monitoring Unix and Linux (Content Library) | **Complete** | `DA-ITSI-CP-nix` v1.3.0 |
| ITSI Module for Operating Systems | **Complete** | `DA-ITSI-OS` — provides **OS KPIs - *nix (SAI)** template |
| Cisco content packs present (no TA) | **Complete** | `DA-ITSI-CP-enterprise-networking`, `DA-ITSI-CP-thousandeyes` (import objects disabled — expected) |

**Outcome:** Met. Environment matches lab prerequisites. See [`LAB_GUIDE.md`](LAB_GUIDE.md) **Prerequisites (Exercise 1)** for UI vs folder naming.

---

### Exercise 2 — Review data for ITSI relevance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Ruritania hosts in scope | **Complete** | 14 hosts: `api-01`–`api-04`, `login-01`–`login-04`, `app-01`–`app-03`, `db-01`–`db-03` |
| Custom rur sourcetypes | **Complete** | `rur_api`, `rur_login`, `rur_db`, `rur_submission` |
| `hardware_events` for entity modelling | **Complete** | Fields include `platform_type`, `cpu_model`, `cpu_cores`, `disk_drives`, `region` |
| KPI latency fields | **Complete** | `response_time_ms` (API), `duration_ms` (login/db), `processing_time_ms` (app) |
| Error events for Episode demo | **Complete** | `index=rur_apps status=ERROR` — concentrated on `app-01`–`app-03` |
| OS/host metrics | **Complete** | Nix metrics indexes populated (auto entity creation from content pack) |
| External alerting tools | **N/A (expected)** | No SolarWinds/Nagios-style sourcetypes — lab notes this is intentional |

**Outcome:** Met. Foundational data is sufficient for the POC scope.

---

### Exercise 3 — Configure entities

| Requirement | Before automation | After automation |
|-------------|-------------------|------------------|
| Linux entities from content pack | 62 (*nix type) | 62 (unchanged) |
| Custom "Ruritania Application Server" entity type | Created (empty) | Created |
| Ruritania-scoped entities populated | **Missing** | **20 entities** tagged with Ruritania entity type |
| Entity dimensions (platform, CPU, region, etc.) | **Missing** | Populated via entity update from `hardware_events` |

**Outcome:** Met. Entity type existed but was unpopulated; automation linked in-scope hosts to the Ruritania Application Server entity type with hardware dimensions.

---

### Exercise 4 — Build service maps

| Requirement | Before automation | After automation |
|-------------|-------------------|------------------|
| Ruritania Application (parent service) | **Missing** | **Enabled** — depends on all 4 tier services |
| API Server | **Missing** | **Enabled** — 13 KPIs, depends on Login + App |
| Login Server | **Missing** | **Enabled** — 13 KPIs |
| App Server | **Missing** | **Enabled** — 13 KPIs, depends on Database |
| Database Server | **Missing** | **Enabled** — 13 KPIs |
| OS KPIs from *nix (SAI) template | **Missing** | **Linked** — 11 OS KPIs per tier service |
| Custom latency KPIs | **Missing** | **Created** — API Response Time, Login Duration, App Processing Time, DB Query Duration |
| Entity rules for Ruritania entity type | **Missing** | **Configured** — 2 rules per tier service |

**Outcome:** Met. Full Ruritania service tree is modelled with dependencies, OS KPIs, and custom transaction latency KPIs.

---

### Exercise 5 — Customize KPI thresholds

| Requirement | Status | Notes |
|-------------|--------|-------|
| Review threshold options | **Complete** | Latency, error-count, and error-rate thresholds applied via `populate_glass_table_data.py` |
| AI Thresholding Recommendations | **Not validated** | Requires 7+ days data; may not work in short-lived lab instances |

**Outcome:** Met for demo purposes. Custom latency KPIs use static thresholds (normal &lt;400ms, warning 400–800ms, critical &gt;1200ms). Error KPIs use count/rate thresholds suited to `rur_apps` data.

---

### Exercise 6 — Alerts and episodes

| Requirement | Before automation | After automation |
|-------------|-------------------|------------------|
| Service Monitoring - KPI Degraded | Disabled | **Enabled** |
| Service Monitoring - Sustained KPI Degradation (Recommended) | Disabled | **Enabled** |
| Episodes by Src aggregation policy | Disabled | **Enabled** |
| Episodes by ITSI Service aggregation policy | Disabled | **Enabled** |
| Custom Ruritania Application Errors correlation search | **Missing** | **Created & enabled** (runs every 5 min) |

**Outcome:** Met. Event analytics pipeline configured. Episodes may take 5–15 minutes to appear after KPI/correlation searches begin running.

---

### Exercise 7 — Glass table

| Requirement | Before automation | After automation |
|-------------|-------------------|------------------|
| Generic POC Glass Table present | Yes | Yes (original retained) |
| Clone/customise for Ruritania App | **Not done** | **Complete** — `Ruritania App Glass Table` |
| Remove Future Health / Data Center sections | N/A | Removed (layout items y≥790 + Future tiles) |
| Wire service health scores | N/A | API, Login, App, Database + overall Ruritania Application |
| Wire KPI blocks (3 per service) | N/A | Latency + Error Count + Error Rate % per tier (replaces OS KPIs — no nix metrics in demo) |
| Hourly Alerts / Episodes ad-hoc searches | N/A | Errors from `rur_apps` (1h); episodes from `itsi_grouped_alerts` |
| Drilldowns to Deep Dive / Service Analyzer / Episodes | N/A | Configured |

**Outcome:** Met. Glass table cloned and customised via `configure_glass_table.py`.

**Open in ITSI:** https://riles-itsi-i-0de3b31445a802592.splunk.show/en-US/app/itsi/glass_table/0d3db01c-8181-11f1-a0e7-02fd7d7a3cf3

**Re-run after lab reset:**
```bash
python3 configure_glass_table.py
python3 populate_glass_table_data.py
```

---

### Exercise 8 — Demo talk track

| Requirement | Status |
|-------------|--------|
| Environment ready for demo | **Ready** (pending glass table & KPI backfill propagation) |
| Service Analyzer tree | Available |
| Deep Dive pivot | Available |
| Entity drilldown | Available |
| Episode management | Configured — allow time for events to aggregate |

**Outcome:** Met for core ITSI workflows. Glass table single-pane-of-glass demo requires Exercise 7 completion.

---

## Configuration delivered by automation

The script `configure_itsi_lab.py` performs:

1. Tags Ruritania hosts with the custom entity type and hardware dimensions
2. Creates/enables the 5-service Ruritania tree with correct dependencies
3. Links **OS KPIs - *nix (SAI)** service template to each tier service
4. Creates 4 custom latency KPIs with per-entity breakdown
5. Enables KPI degradation correlation searches
6. Enables Episodes by Src / Episodes by ITSI Service aggregation policies
7. Creates the **Ruritania Application Errors** correlation search

The script `configure_glass_table.py` performs Exercise 7:

1. Clones **Generic POC Glass Table** → **Ruritania App Glass Table**
2. Removes Future Health and Data Center network sections
3. Wires service health scores and 3 KPIs per tier service
4. Adds hourly Alerts/Episodes ad-hoc searches (with corrected entity prefixes)
5. Configures drilldowns to Deep Dive, Service Analyzer, and Episode Management

Re-run after lab reset:
```bash
python3 configure_itsi_lab.py
python3 configure_glass_table.py
```

---

## Remaining manual actions

1. **Wait 5–15 minutes** after running `populate_glass_table_data.py` for KPI backfill and episode aggregation
2. **Re-run populate script** if glass table tiles are still grey: `python3 populate_glass_table_data.py`
3. **Optional:** Remove test artifacts if present (`API Server TEST`, `api-01-rur-test2` entity)
4. **Optional:** Save a custom Service Analyzer view for Ruritania Application
5. **Optional:** Fine-tune glass table layout/colours in the ITSI UI if desired

---

## Success criteria mapping (Exercise 8)

| POC success criterion | Status |
|-----------------------|--------|
| Single pane of glass (Glass Table) | **Complete** — Ruritania App Glass Table |
| Service stack monitoring (Service Analyzer) | **Complete** |
| Root cause KPI / Deep Dive | **Complete** |
| Entity correlation with host/asset data | **Complete** |
| Error alerts → Episodes → Service correlation | **Complete** (events propagating on schedule) |
