#!/usr/bin/env python3
"""Exercise 7: Clone and customise Generic POC Glass Table for Ruritania App."""

from __future__ import annotations

import copy
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from pathlib import Path

from splunk_config import load_splunk_config

HOST, USER, PASS = load_splunk_config()
BASE = f"https://{HOST}:8089"
ORIGINAL_KEY = "79aa6fff-a076-11f0-b438-0e5379f5040d"
GLASS_TITLE = "Ruritania App Glass Table"

SERVICES = {
    "API Server": {
        "service_id": "36b1e68b-0abe-41b5-b3c7-f92f77d5e131",
        "shkpi": "SHKPI-36b1e68b-0abe-41b5-b3c7-f92f77d5e131",
        "entity_prefix": "api",
        "label_viz": "viz_105ZLlWS",
        "health_viz": "viz_1ZF2UAxR",
        "row_y": 440,
        "kpis": [
            ("68e40597-2a2a-498b-89ce-c813a0e4cff4", "API Response Time", ["viz_2dZHA0Tf"]),
            ("44167631-3cf7-44e6-9272-622a153e3cd4", "API Error Count", ["viz_hxY0zBZW"]),
            ("2174e5f9-d97e-49f9-9cfc-592ad3d07b21", "API Error Rate %", ["viz_BCzQQqcS"]),
        ],
        "alert_viz": ["viz_TwcpmT2e"],
        "episode_viz": ["viz_Dbn9RAhf"],
    },
    "Login Server": {
        "service_id": "329c4f16-547e-47d6-825c-290b48d0bad3",
        "shkpi": "SHKPI-329c4f16-547e-47d6-825c-290b48d0bad3",
        "entity_prefix": "login",
        "label_viz": "viz_YEexCVuK",
        "health_viz": "viz_wgK2ImFs",
        "row_y": 520,
        "kpis": [
            ("98557b5a-a043-46c0-9702-920b5310a632", "Login Duration", ["viz_SQOQmceS"]),
            ("7b40b845-cd7f-4567-973a-d12422b634af", "Login Error Count", ["viz_svv5CfZ0"]),
            ("a8fbf0a8-7911-4c4d-a10b-b05710f8c9f5", "Login Error Rate %", ["viz_hG5aZS3A"]),
        ],
        "alert_viz": ["viz_OgGuf1dV"],
        "episode_viz": ["viz_mv1BCEWn"],
    },
    "App Server": {
        "service_id": "771742a2-5369-497a-ac93-d2616301f846",
        "shkpi": "SHKPI-771742a2-5369-497a-ac93-d2616301f846",
        "entity_prefix": "app",
        "label_viz": "viz_pYt5KZb7",
        "health_viz": "viz_KFb9vlmT",
        "row_y": 600,
        "kpis": [
            ("abb08e0b-6431-4ef6-90ef-a643ea0c760a", "App Processing Time", ["viz_BLy7fzmI"]),
            ("d2d4b2f1-6fa1-471d-b6e6-ed27a1698ff2", "App Error Count", ["viz_fwl4cxzG"]),
            ("f4c57954-6772-414a-9dc9-a295d161074f", "App Error Rate %", ["viz_0Ygj0pAK"]),
        ],
        "alert_viz": ["viz_oDJ3L9GO"],
        "episode_viz": ["viz_mtQ2FNXr"],
    },
    "Database Server": {
        "service_id": "fff3f9d9-cc1d-4a70-b208-d05902cf4dcb",
        "shkpi": "SHKPI-fff3f9d9-cc1d-4a70-b208-d05902cf4dcb",
        "entity_prefix": "db",
        "label_viz": "viz_2vjE75FD",
        "health_viz": "viz_mZLUkONs",
        "row_y": 680,
        "kpis": [
            ("54816fb4-3093-4ce4-84ed-51f67a011b59", "DB Query Duration", ["viz_rG6mfGeU"]),
            ("6703319e-9ce8-4484-95e6-3b0a0febeaf7", "DB Error Count", ["viz_nAWdwUnQ"]),
            ("5c868ca4-2ad9-43c1-a6c0-ab08b82aded9", "DB Error Rate %", ["viz_FKn03peO"]),
        ],
        "alert_viz": ["viz_64s3NyJN"],
        "episode_viz": ["viz_3MrQoMVf"],
    },
}

OVERALL = {
    "service_id": "9a3b7069-bf60-4d76-8af2-c88ab2194f23",
    "shkpi": "SHKPI-9a3b7069-bf60-4d76-8af2-c88ab2194f23",
    "health_viz": "viz_zOW7aA05",
}

FUTURE_VIZ = {"viz_MrtaluGJ", "viz_IICM3FCg", "viz_yIiOJILg", "viz_1J0YqjQa"}
REMOVE_VIZ = FUTURE_VIZ | {
    "viz_CnF2jfXF",  # Data Center Network header
    "viz_q4Mknf8I",  # Thousand Eyes
    "viz_4kUIgUBQ",  # Future/predictive tile
}
REMOVE_Y_MIN = 790

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def req(path: str, *, method: str = "GET", json_body=None, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"Authorization": f"Basic {b64encode(f'{USER}:{PASS}'.encode()).decode()}", "Accept": "application/json"}
    body = json.dumps(json_body).encode() if json_body is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=180) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw.strip().startswith("{") else raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def kpi_ds(ds_key: str, name: str, kpi_id: str, service_id: str) -> dict:
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


def adhoc_ds(ds_key: str, name: str, query: str) -> dict:
    return {"type": "ds.search", "name": name, "options": {"query": query}}


def deep_dive_handler(service_id: str, kpi_id: str | None = None) -> list:
    url = f"/en-US/app/itsi/deep_dive?serviceId={service_id}"
    if kpi_id:
        url += f"&kpiId={kpi_id}"
    url += "&earliest=$global_time.earliest$&latest=$global_time.latest$"
    return [{"type": "drilldown.deepDiveObject", "options": {"url": url, "newTab": True, "type": "saved_deep_dive"}}]


def service_analyzer_handler(service_id: str) -> list:
    url = (
        f"/en-US/app/itsi/service_analyzer?service={service_id}"
        "&earliest=$global_time.earliest$&latest=$global_time.latest$"
    )
    return [{"type": "drilldown.homeViewObject", "options": {"url": url, "newTab": True, "type": "saved_home_view"}}]


def event_mgmt_handler() -> list:
    return [
        {
            "type": "drilldown.eventManagementObject",
            "options": {
                "url": "/en-US/app/itsi/itsi_event_management?earliest=$global_time.earliest$&latest=$global_time.latest$",
                "newTab": True,
                "type": "saved_event_management",
            },
        }
    ]


def bind_singlevalue(viz: dict, ds_key: str, handlers: list | None = None) -> None:
    viz.setdefault("dataSources", {})["primary"] = ds_key
    opts = viz.setdefault("options", {})
    opts["majorColor"] = '> primary | seriesByName("alert_color") | lastPoint()'
    opts["sparklineValues"] = '> primary | seriesByName("alert_value")'
    opts["sparklineDisplay"] = "off"
    opts["trendDisplay"] = "off"
    opts["showSparklineTooltip"] = True
    if handlers is not None:
        viz["eventHandlers"] = handlers


def build_glass_table(source: dict) -> dict:
    gt = copy.deepcopy(source)
    gt.pop("_key", None)
    gt.pop("mod_time", None)
    gt.pop("mod_timestamp", None)
    gt["title"] = GLASS_TITLE
    gt["description"] = "Ruritania Application POC glass table - Exercise 7"
    gt["identifying_name"] = GLASS_TITLE

    definition = gt["definition"]
    definition["title"] = GLASS_TITLE
    data_sources = definition["dataSources"]
    visualizations = definition["visualizations"]
    structure = definition["layout"]["layoutDefinitions"]["layout_1"]["structure"]

    # Remove data center / future sections from layout
    structure[:] = [
        item
        for item in structure
        if item.get("item") not in REMOVE_VIZ and item.get("position", {}).get("y", 0) < REMOVE_Y_MIN
    ]

    # Update section headers
    header_updates = {
        "viz_wnAwtjCZ": "**Ruritania Application Health**",
        "viz_kyh2zxEG": "Ruritania Application Health and Alerts",
        "viz_rpFTbTKk": "Application Services",
        "viz_j3asRtV9": "Alerts",
        "viz_Tjb7pOyk": "Services",
    }
    for vid, text in header_updates.items():
        if vid in visualizations:
            visualizations[vid].setdefault("options", {})["markdown"] = text

    # Overall application health score
    overall_ds = "ds_rur_overall_health"
    data_sources[overall_ds] = kpi_ds(overall_ds, "Ruritania Application - ServiceHealthScore", OVERALL["shkpi"], OVERALL["service_id"])
    bind_singlevalue(visualizations[OVERALL["health_viz"]], overall_ds, service_analyzer_handler(OVERALL["service_id"]))

    for svc_name, cfg in SERVICES.items():
        # Service label
        if cfg["label_viz"] in visualizations:
            visualizations[cfg["label_viz"]].setdefault("options", {})["markdown"] = svc_name

        # Service health tile
        health_ds = f"ds_{cfg['service_id'][:8]}_health"
        data_sources[health_ds] = kpi_ds(health_ds, f"{svc_name} - ServiceHealthScore", cfg["shkpi"], cfg["service_id"])
        bind_singlevalue(visualizations[cfg["health_viz"]], health_ds, deep_dive_handler(cfg["service_id"]))

        # KPI tiles (3 per service)
        for kpi_id, kpi_name, viz_ids in cfg["kpis"]:
            if not kpi_id:
                continue
            ds_key = f"ds_{kpi_id[:8]}"
            data_sources[ds_key] = kpi_ds(ds_key, f"{svc_name} - {kpi_name}", kpi_id, cfg["service_id"])
            for vid in viz_ids:
                if vid in visualizations:
                    bind_singlevalue(visualizations[vid], ds_key, deep_dive_handler(cfg["service_id"], kpi_id))

        # Hourly errors from rur_apps (immediate visibility)
        alert_ds = f"ds_{cfg['entity_prefix']}_alerts"
        data_sources[alert_ds] = adhoc_ds(
            alert_ds,
            f"{svc_name} - Hourly Errors",
            (
                f"index=rur_apps host={cfg['entity_prefix']}* (status>=400 OR isnotnull(error)) earliest=-1h "
                "| timechart span=5m count as alert_value "
                "| eval alert_color=case(alert_value>50,\"#FF8762\",alert_value>10,\"#FFB800\",true(),\"#99D18B\")"
            ),
        )
        for vid in cfg["alert_viz"]:
            if vid in visualizations:
                bind_singlevalue(visualizations[vid], alert_ds, event_mgmt_handler())

        # Hourly episodes ad-hoc search (fixed typo: entity_prefix per service)
        episode_ds = f"ds_{cfg['entity_prefix']}_episodes"
        data_sources[episode_ds] = adhoc_ds(
            episode_ds,
            f"{svc_name} - Hourly Episodes",
            (
                f"index=itsi_grouped_alerts entity_name={cfg['entity_prefix']}* earliest=-1h "
                "| timechart span=5m dc(itsi_group_id) as alert_value "
                "| eval alert_color=case(alert_value>0,\"#FFB800\",true(),\"#99D18B\")"
            ),
        )
        for vid in cfg["episode_viz"]:
            if vid in visualizations:
                bind_singlevalue(visualizations[vid], episode_ds, event_mgmt_handler())

        # Service analyzer drilldown on first column of each row
        row_home = {
            440: "viz_ZNZQ1FfT",
            520: "viz_tIFljW1p",
            600: "viz_kBnmqNqx",
            680: "viz_px5M3Dsp",
        }.get(cfg["row_y"])
        if row_home and row_home in visualizations:
            visualizations[row_home]["eventHandlers"] = service_analyzer_handler(cfg["service_id"])

    definition["layout"]["tabs"]["items"][0]["label"] = "Ruritania Application"

    # Drop visualizations removed from layout — ITSI requires every viz to appear in structure
    layout_viz_ids = {item["item"] for item in structure}
    orphan_viz = set(visualizations) - layout_viz_ids
    for vid in orphan_viz:
        del visualizations[vid]

    # Drop data sources no longer referenced by any remaining visualization
    referenced_ds: set[str] = set()

    def collect_ds(obj) -> None:
        if isinstance(obj, dict):
            if "primary" in obj and isinstance(obj["primary"], str):
                referenced_ds.add(obj["primary"])
            for v in obj.values():
                collect_ds(v)
        elif isinstance(obj, list):
            for i in obj:
                collect_ds(i)

    collect_ds(visualizations)
    orphan_ds = set(data_sources) - referenced_ds
    for ds_key in orphan_ds:
        del data_sources[ds_key]

    return gt


def main() -> None:
    local_path = Path(__file__).parent / "glass_table_original.json"
    if local_path.exists():
        source = json.loads(local_path.read_text())
    else:
        _, source = req(f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{ORIGINAL_KEY}", params={"output_mode": "json"})

    payload = build_glass_table(source)

    # Delete existing clone if re-running
    _, existing = req("/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table", params={"output_mode": "json", "count": "0"})
    if isinstance(existing, list):
        for gt in existing:
            if gt.get("title") == GLASS_TITLE:
                req(f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{gt['_key']}", method="DELETE")

    status, result = req("/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table", method="POST", json_body=payload)
    print(f"Create glass table: HTTP {status}")
    if status == 200:
        key = result.get("_key")
        viz_count = len(payload["definition"]["visualizations"])
        layout_count = len(payload["definition"]["layout"]["layoutDefinitions"]["layout_1"]["structure"])
        print(f"Created: {GLASS_TITLE} key={key}")
        print(f"Visualizations: {viz_count}, Layout blocks: {layout_count}")
        print(f"Open: https://{HOST}/en-US/app/itsi/glass_table/{key}")
    else:
        print(result)
        raise SystemExit(1)

    out = Path(__file__).parent / "glass_table_ruritania.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"Saved local copy: {out}")


if __name__ == "__main__":
    main()
