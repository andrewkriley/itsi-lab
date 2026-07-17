#!/usr/bin/env python3
"""Apply KPI thresholds, backfill, error KPIs, and glass-table data-source fixes."""

from __future__ import annotations

import copy
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from typing import Any

from splunk_config import load_splunk_config

HOST, USER, PASS = load_splunk_config()
BASE = f"https://{HOST}:8089"
GLASS_TITLE = "Ruritania App Glass Table"
BACKFILL_EARLIEST = "-1d"

SERVICE_IDS = {
    "API Server": "36b1e68b-0abe-41b5-b3c7-f92f77d5e131",
    "Login Server": "329c4f16-547e-47d6-825c-290b48d0bad3",
    "App Server": "771742a2-5369-497a-ac93-d2616301f846",
    "Database Server": "fff3f9d9-cc1d-4a70-b208-d05902cf4dcb",
    "Ruritania Application": "9a3b7069-bf60-4d76-8af2-c88ab2194f23",
}

LATENCY_KPIS = {
    "API Server": ("API Response Time", "index=rur_apps host=api* | stats avg(response_time_ms) as value by host"),
    "Login Server": ("Login Duration", "index=rur_apps host=login* | stats avg(duration_ms) as value by host"),
    "App Server": ("App Processing Time", "index=rur_apps sourcetype=rur_submission host=app* | stats avg(processing_time_ms) as value by host"),
    "Database Server": ("DB Query Duration", "index=rur_apps host=db* | stats avg(duration_ms) as value by host"),
}

ERROR_KPIS = {
    "API Server": ("API Error Count", "index=rur_apps host=api* (status>=400 OR isnotnull(error)) | stats count as value by host"),
    "Login Server": ("Login Error Count", "index=rur_apps host=login* (status>=400 OR isnotnull(error)) | stats count as value by host"),
    "App Server": ("App Error Count", "index=rur_apps host=app* (status>=400 OR isnotnull(error)) | stats count as value by host"),
    "Database Server": ("DB Error Count", "index=rur_apps host=db* (status>=400 OR isnotnull(error)) | stats count as value by host"),
}

ERROR_RATE_KPIS = {
    "API Server": (
        "API Error Rate %",
        "index=rur_apps host=api* | stats count as total count(eval(status>=400 OR isnotnull(error))) as errors by host | eval value=if(total=0, 0, round(100*errors/total, 2))",
    ),
    "Login Server": (
        "Login Error Rate %",
        "index=rur_apps host=login* | stats count as total count(eval(status>=400 OR isnotnull(error))) as errors by host | eval value=if(total=0, 0, round(100*errors/total, 2))",
    ),
    "App Server": (
        "App Error Rate %",
        "index=rur_apps host=app* | stats count as total count(eval(status>=400 OR isnotnull(error))) as errors by host | eval value=if(total=0, 0, round(100*errors/total, 2))",
    ),
    "Database Server": (
        "DB Error Rate %",
        "index=rur_apps host=db* | stats count as total count(eval(status>=400 OR isnotnull(error))) as errors by host | eval value=if(total=0, 0, round(100*errors/total, 2))",
    ),
}

GLASS_KPI_SLOTS = {
    "API Server": {
        "latency": ("68e40597-2a2a-498b-89ce-c813a0e4cff4", ["viz_2dZHA0Tf"]),
        "error_count": ("44167631-3cf7-44e6-9272-622a153e3cd4", ["viz_hxY0zBZW"]),
        "error_rate": ("2174e5f9-d97e-49f9-9cfc-592ad3d07b21", ["viz_BCzQQqcS"]),
        "entity_prefix": "api",
        "alert_viz": ["viz_TwcpmT2e"],
        "episode_viz": ["viz_Dbn9RAhf"],
    },
    "Login Server": {
        "latency": ("98557b5a-a043-46c0-9702-920b5310a632", ["viz_SQOQmceS"]),
        "error_count": ("7b40b845-cd7f-4567-973a-d12422b634af", ["viz_svv5CfZ0"]),
        "error_rate": ("a8fbf0a8-7911-4c4d-a10b-b05710f8c9f5", ["viz_hG5aZS3A"]),
        "entity_prefix": "login",
        "alert_viz": ["viz_OgGuf1dV"],
        "episode_viz": ["viz_mv1BCEWn"],
    },
    "App Server": {
        "latency": ("abb08e0b-6431-4ef6-90ef-a643ea0c760a", ["viz_BLy7fzmI"]),
        "error_count": ("d2d4b2f1-6fa1-471d-b6e6-ed27a1698ff2", ["viz_fwl4cxzG"]),
        "error_rate": ("f4c57954-6772-414a-9dc9-a295d161074f", ["viz_0Ygj0pAK"]),
        "entity_prefix": "app",
        "alert_viz": ["viz_oDJ3L9GO"],
        "episode_viz": ["viz_mtQ2FNXr"],
    },
    "Database Server": {
        "latency": ("54816fb4-3093-4ce4-84ed-51f67a011b59", ["viz_rG6mfGeU"]),
        "error_count": ("6703319e-9ce8-4484-95e6-3b0a0febeaf7", ["viz_nAWdwUnQ"]),
        "error_rate": ("5c868ca4-2ad9-43c1-a6c0-ab08b82aded9", ["viz_FKn03peO"]),
        "entity_prefix": "db",
        "alert_viz": ["viz_64s3NyJN"],
        "episode_viz": ["viz_3MrQoMVf"],
    },
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def req(
    path: str,
    *,
    method: str = "GET",
    params: dict[str, str] | None = None,
    json_body: Any = None,
    data: dict[str, str] | None = None,
) -> tuple[int, Any]:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    auth = b64encode(f"{USER}:{PASS}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=180) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def get_all(path: str) -> list[dict[str, Any]]:
    _, data = req(path, params={"output_mode": "json", "count": "0"})
    return data if isinstance(data, list) else []


def latency_thresholds() -> dict[str, Any]:
    return {
        "baseSeverityLabel": "normal",
        "baseSeverityColor": "#99D18B",
        "baseSeverityValue": 1,
        "baseSeverityColorLight": "#D4EDDA",
        "thresholdLevels": [
            {
                "severityLabel": "low",
                "severityValue": 2,
                "severityColor": "#FFE98B",
                "severityColorLight": "#FFF3CD",
                "thresholdValue": 400,
            },
            {
                "severityLabel": "medium",
                "severityValue": 3,
                "severityColor": "#FFB800",
                "severityColorLight": "#FFE0B2",
                "thresholdValue": 800,
            },
            {
                "severityLabel": "high",
                "severityValue": 4,
                "severityColor": "#FF8762",
                "severityColorLight": "#FFCDD2",
                "thresholdValue": 1200,
            },
        ],
        "isMaxStatic": False,
        "isMinStatic": False,
        "thresholdDirection": "above",
    }


def count_thresholds() -> dict[str, Any]:
    return {
        "baseSeverityLabel": "normal",
        "baseSeverityColor": "#99D18B",
        "baseSeverityValue": 1,
        "baseSeverityColorLight": "#D4EDDA",
        "thresholdLevels": [
            {
                "severityLabel": "low",
                "severityValue": 2,
                "severityColor": "#FFE98B",
                "severityColorLight": "#FFF3CD",
                "thresholdValue": 50,
            },
            {
                "severityLabel": "medium",
                "severityValue": 3,
                "severityColor": "#FFB800",
                "severityColorLight": "#FFE0B2",
                "thresholdValue": 150,
            },
            {
                "severityLabel": "high",
                "severityValue": 4,
                "severityColor": "#FF8762",
                "severityColorLight": "#FFCDD2",
                "thresholdValue": 300,
            },
        ],
        "isMaxStatic": False,
        "isMinStatic": False,
        "thresholdDirection": "above",
    }


def rate_thresholds() -> dict[str, Any]:
    return {
        "baseSeverityLabel": "normal",
        "baseSeverityColor": "#99D18B",
        "baseSeverityValue": 1,
        "baseSeverityColorLight": "#D4EDDA",
        "thresholdLevels": [
            {
                "severityLabel": "low",
                "severityValue": 2,
                "severityColor": "#FFE98B",
                "severityColorLight": "#FFF3CD",
                "thresholdValue": 2,
            },
            {
                "severityLabel": "medium",
                "severityValue": 3,
                "severityColor": "#FFB800",
                "severityColorLight": "#FFE0B2",
                "thresholdValue": 5,
            },
            {
                "severityLabel": "high",
                "severityValue": 4,
                "severityColor": "#FF8762",
                "severityColorLight": "#FFCDD2",
                "thresholdValue": 10,
            },
        ],
        "isMaxStatic": False,
        "isMinStatic": False,
        "thresholdDirection": "above",
    }


def strip_generated_kpi_fields(kpi: dict[str, Any]) -> None:
    for field in (
        "search",
        "search_entities",
        "search_aggregate",
        "search_time_series_entities",
        "search_time_series_aggregate",
        "search_alert_entities",
        "search_alert_aggregate",
    ):
        kpi.pop(field, None)


def apply_kpi_patch(
    kpi: dict[str, Any],
    *,
    base_search: str,
    thresholds: dict[str, Any],
    unit: str,
) -> dict[str, Any]:
    patched = copy.deepcopy(kpi)
    patched["base_search"] = base_search
    patched["search_alert"] = base_search
    patched["threshold_field"] = "value"
    patched["aggregate_thresholds"] = thresholds
    patched["entity_thresholds"] = thresholds
    patched["backfill_enabled"] = True
    patched["backfill_earliest_time"] = BACKFILL_EARLIEST
    patched["gap_severity"] = "normal"
    patched["unit"] = unit
    patched["is_entity_breakdown"] = True
    patched["entity_id_fields"] = "host"
    patched["entity_breakdown_id_fields"] = "host"
    strip_generated_kpi_fields(patched)
    return patched


def find_kpi(service: dict[str, Any], title: str) -> dict[str, Any] | None:
    for kpi in service.get("kpis") or []:
        if kpi.get("title") == title:
            return kpi
    return None


def create_kpi(
    service_id: str,
    title: str,
    base_search: str,
    unit: str,
    thresholds: dict[str, Any],
    *,
    statop: str,
) -> str | None:
    status, res = req(
        "/servicesNS/nobody/SA-ITOA/itoa_interface/kpi",
        method="POST",
        json_body={
            "title": title,
            "description": f"Ruritania demo KPI for glass table: {title}",
            "service_id": service_id,
            "search_type": "adhoc",
            "base_search": base_search,
            "search_alert": base_search,
            "threshold_field": "value",
            "unit": unit,
            "aggregate_statop": statop,
            "entity_statop": statop,
            "alert_on": "both",
            "urgency": "5",
            "alert_period": "15",
            "search_alert_earliest": "15",
            "is_entity_breakdown": True,
            "entity_id_fields": "host",
            "entity_breakdown_id_fields": "host",
            "aggregate_thresholds": thresholds,
            "entity_thresholds": thresholds,
            "backfill_enabled": True,
            "backfill_earliest_time": BACKFILL_EARLIEST,
            "gap_severity": "normal",
            "enabled": True,
        },
    )
    if status == 200 and isinstance(res, dict):
        return res.get("_key")
    print(f"[WARN] create KPI {title}: HTTP {status} {str(res)[:200]}")
    return None


def configure_kpis() -> dict[str, dict[str, str]]:
    """Return service -> {slot: kpi_id} mapping for glass table wiring."""
    mapping: dict[str, dict[str, str]] = {}
    services = {s["title"]: s for s in get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/service")}

    for service_title, (latency_title, latency_search) in LATENCY_KPIS.items():
        service = services[service_title]
        kpi_updates: list[dict[str, Any]] = []
        slot_map: dict[str, str] = {}

        latency = find_kpi(service, latency_title)
        if latency:
            kpi_updates.append(
                apply_kpi_patch(latency, base_search=latency_search, thresholds=latency_thresholds(), unit="ms")
            )
            slot_map["latency"] = latency["_key"]
            print(f"[OK] patched latency KPI: {service_title} / {latency_title}")

        for slot_name, (title, search), thresholds, unit, statop_hint in (
            ("error_count", ERROR_KPIS[service_title], count_thresholds(), "events", "sum"),
            ("error_rate", ERROR_RATE_KPIS[service_title], rate_thresholds(), "%", "avg"),
        ):
            existing = find_kpi(service, title)
            if existing:
                patched = apply_kpi_patch(existing, base_search=search, thresholds=thresholds, unit=unit)
                patched["aggregate_statop"] = statop_hint
                patched["entity_statop"] = statop_hint
                kpi_updates.append(patched)
                slot_map[slot_name] = existing["_key"]
                print(f"[OK] patched {title}")
            else:
                key = create_kpi(service["_key"], title, search, unit, thresholds, statop=statop_hint)
                if key:
                    slot_map[slot_name] = key
                    print(f"[OK] created {title} ({key})")

        if kpi_updates:
            status, res = req(
                "/servicesNS/nobody/SA-ITOA/itoa_interface/service/bulk_update?is_partial_data=1",
                method="POST",
                json_body=[{"_key": service["_key"], "title": service["title"], "kpis": kpi_updates}],
            )
            print(f"[{'OK' if status == 200 else 'ERR'}] bulk_update {service_title}: HTTP {status}")
            if status != 200:
                print(str(res)[:300])

        mapping[service_title] = slot_map

    return mapping


def enable_service_health_backfill() -> None:
    updates = []
    for title, service_id in SERVICE_IDS.items():
        updates.append(
            {
                "_key": service_id,
                "title": title,
                "service_health_backfill_enabled": True,
                "service_health_backfill_earliest_time": BACKFILL_EARLIEST,
            }
        )
    status, res = req(
        "/servicesNS/nobody/SA-ITOA/itoa_interface/service/bulk_update?is_partial_data=1",
        method="POST",
        json_body=updates,
    )
    print(f"[{'OK' if status == 200 else 'ERR'}] service health backfill: HTTP {status}")
    if status != 200:
        print(str(res)[:300])


def fix_correlation_search() -> None:
    search = """index=rur_apps (status>=400 OR isnotnull(error))
| eval service_name=case(
    like(host, "api%"), "API Server",
    like(host, "app%"), "App Server",
    like(host, "login%"), "Login Server",
    like(host, "db%"), "Database Server",
    true(), "Unknown Service")"""
    status, res = req(
        "/servicesNS/nobody/SA-ITOA/saved/searches/Ruritania%20Application%20Errors",
        method="POST",
        data={
            "search": search,
            "disabled": "0",
            "action.itsi_event_generator": "1",
            "action.itsi_event_generator.param.severity": "high",
            "action.itsi_event_generator.param.title": "Ruritania Application Error on $host$",
        },
    )
    print(f"[{'OK' if status == 200 else 'ERR'}] correlation search fix: HTTP {status}")


def kpi_ds(name: str, kpi_id: str, service_id: str) -> dict[str, Any]:
    return {
        "type": "ds.search",
        "name": name,
        "options": {
            "query": (
                f"`get_full_itsi_summary_kpi({kpi_id})` `service_level_kpi_only` "
                "| timechart cont=false latest(alert_value) AS alert_value, latest(alert_color) AS alert_color"
            )
        },
        "meta": {"kpiID": kpi_id, "serviceID": service_id},
    }


def adhoc_ds(name: str, query: str) -> dict[str, Any]:
    return {"type": "ds.search", "name": name, "options": {"query": query}}


def bind_singlevalue(viz: dict[str, Any], ds_key: str) -> None:
    viz.setdefault("dataSources", {})["primary"] = ds_key
    opts = viz.setdefault("options", {})
    opts["majorColor"] = '> primary | seriesByName("alert_color") | lastPoint()'
    opts["sparklineValues"] = '> primary | seriesByName("alert_value")'
    opts["sparklineDisplay"] = "off"
    opts["trendDisplay"] = "off"
    opts["showSparklineTooltip"] = True


def update_glass_table(kpi_mapping: dict[str, dict[str, str]]) -> None:
    tables = get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table")
    gt = next((t for t in tables if t.get("title") == GLASS_TITLE), None)
    if not gt:
        print("[WARN] glass table not found; run configure_glass_table.py first")
        return

    definition = gt["definition"]
    data_sources = definition["dataSources"]
    visualizations = definition["visualizations"]

    for service_title, slots in GLASS_KPI_SLOTS.items():
        service_id = SERVICE_IDS[service_title]
        svc_map = kpi_mapping.get(service_title, {})
        prefix = slots["entity_prefix"]

        for slot in ("latency", "error_count", "error_rate"):
            kpi_id = svc_map.get(slot) or (slots[slot][0] if slots[slot][0] else None)
            viz_ids = slots[slot][1]
            if not kpi_id:
                continue
            ds_key = f"ds_{kpi_id[:8]}"
            data_sources[ds_key] = kpi_ds(f"{service_title} - {slot}", kpi_id, service_id)
            for vid in viz_ids:
                if vid in visualizations:
                    bind_singlevalue(visualizations[vid], ds_key)

        alert_query = (
            f"index=rur_apps host={prefix}* (status>=400 OR isnotnull(error)) earliest=-1h "
            "| timechart span=5m count as alert_value "
            "| eval alert_color=case(alert_value>50,\"#FF8762\",alert_value>10,\"#FFB800\",true(),\"#99D18B\")"
        )
        alert_ds = f"ds_{prefix}_alerts"
        data_sources[alert_ds] = adhoc_ds(f"{service_title} - Hourly Errors", alert_query)
        for vid in slots["alert_viz"]:
            if vid in visualizations:
                bind_singlevalue(visualizations[vid], alert_ds)

        episode_query = (
            f"index=itsi_grouped_alerts entity_name={prefix}* earliest=-1h "
            "| timechart span=5m dc(itsi_group_id) as alert_value "
            "| eval alert_color=case(alert_value>0,\"#FFB800\",true(),\"#99D18B\")"
        )
        episode_ds = f"ds_{prefix}_episodes"
        data_sources[episode_ds] = adhoc_ds(f"{service_title} - Hourly Episodes", episode_query)
        for vid in slots["episode_viz"]:
            if vid in visualizations:
                bind_singlevalue(visualizations[vid], episode_ds)

    gt_key = gt["_key"]
    payload = copy.deepcopy(gt)
    for field in ("mod_time", "mod_timestamp"):
        payload.pop(field, None)
    status, res = req(
        f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{gt_key}",
        method="POST",
        json_body=payload,
    )
    print(f"[{'OK' if status == 200 else 'ERR'}] glass table update: HTTP {status}")
    if status == 200:
        print(f"Open: https://{HOST}/en-US/app/itsi/glass_table/{gt_key}")
    else:
        print(str(res)[:400])


def wait_for_summary(sample_kpi: str, timeout_sec: int = 120) -> None:
    print(f"Waiting up to {timeout_sec}s for KPI summary data...")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        status, res = req(
            "/services/search/jobs",
            method="POST",
            data={
                "search": (
                    f"search index=itsi_summary kpiid={sample_kpi} "
                    "| stats latest(alert_value) as val count by alert_color | where val!=\"N/A\""
                ),
                "earliest_time": "-24h",
                "latest_time": "now",
                "output_mode": "json",
                "count": "5",
                "exec_mode": "oneshot",
            },
        )
        if status == 200 and isinstance(res, dict) and res.get("results"):
            print(f"[OK] summary populated: {res['results']}")
            return
        time.sleep(15)
    print("[WARN] summary still sparse; backfill may still be running")


def main() -> None:
    print("=== Populate glass table data ===")
    fix_correlation_search()
    kpi_mapping = configure_kpis()
    enable_service_health_backfill()
    update_glass_table(kpi_mapping)
    wait_for_summary("68e40597-2a2a-498b-89ce-c813a0e4cff4")
    print("\nDone. Allow 5-15 minutes for backfill and episode aggregation to fully populate.")


if __name__ == "__main__":
    main()
