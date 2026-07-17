#!/usr/bin/env python3
"""Automate ITSI POC lab configuration against Splunk Show instance."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any

from splunk_config import load_splunk_config

HOST, USER, PASS = load_splunk_config()
BASE = f"https://{HOST}:8089"
RUR_ET_KEY = "6a597f3ef451bd5be609872f"
NIX_TEMPLATE = "SAI-Nix_Service_Template"
SEC_GRP = "default_itsi_security_group"

SERVICES = [
    {
        "title": "Database Server",
        "description": "Database tier for Ruritania Application",
        "depends_on": [],
        "host_prefix": "db",
    },
    {
        "title": "App Server",
        "description": "Application business logic tier",
        "depends_on": ["Database Server"],
        "host_prefix": "app",
    },
    {
        "title": "Login Server",
        "description": "Login authorization tier",
        "depends_on": [],
        "host_prefix": "login",
    },
    {
        "title": "API Server",
        "description": "API tier for Ruritania Application",
        "depends_on": ["Login Server", "App Server"],
        "host_prefix": "api",
    },
    {
        "title": "Ruritania Application",
        "description": "Top-level Ruritania Application service",
        "depends_on": ["API Server", "Login Server", "App Server", "Database Server"],
        "host_prefix": None,
    },
]

CUSTOM_KPIS = [
    (
        "API Server",
        "API Response Time",
        "index=rur_apps host=api* | stats avg(response_time_ms) as value by host",
        "value",
    ),
    (
        "Login Server",
        "Login Duration",
        "index=rur_apps host=login* | stats avg(duration_ms) as value by host",
        "value",
    ),
    (
        "App Server",
        "App Processing Time",
        "index=rur_apps sourcetype=rur_submission host=app* | stats avg(processing_time_ms) as value by host",
        "value",
    ),
    (
        "Database Server",
        "DB Query Duration",
        "index=rur_apps host=db* | stats avg(duration_ms) as value by host",
        "value",
    ),
]

LATENCY_THRESHOLDS = {
    "baseSeverityLabel": "normal",
    "baseSeverityColor": "#99D18B",
    "baseSeverityValue": 1,
    "baseSeverityColorLight": "#D4EDDA",
    "thresholdLevels": [
        {"severityLabel": "low", "severityValue": 2, "severityColor": "#FFE98B", "severityColorLight": "#FFF3CD", "thresholdValue": 400},
        {"severityLabel": "medium", "severityValue": 3, "severityColor": "#FFB800", "severityColorLight": "#FFE0B2", "thresholdValue": 800},
        {"severityLabel": "high", "severityValue": 4, "severityColor": "#FF8762", "severityColorLight": "#FFCDD2", "thresholdValue": 1200},
    ],
    "isMaxStatic": False,
    "isMinStatic": False,
    "thresholdDirection": "above",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


@dataclass
class Result:
    steps: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def log(self, step: str, status: str, detail: str = "") -> None:
        self.steps.append({"step": step, "status": status, "detail": detail})
        print(f"[{status}] {step}" + (f": {detail}" if detail else ""))


RESULT = Result()


def req(
    path: str,
    *,
    params: dict[str, str] | None = None,
    method: str = "GET",
    data: dict[str, str] | None = None,
    json_body: Any = None,
) -> tuple[int, Any]:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    auth = b64encode(f"{USER}:{PASS}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    body = None
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


def run_search(search: str, *, count: int = 200) -> list[dict[str, str]]:
    _, res = req(
        "/services/search/jobs",
        method="POST",
        data={
            "search": search if search.lstrip().startswith(("search", "|")) else "search " + search,
            "earliest_time": "-24h@h",
            "latest_time": "now",
            "output_mode": "json",
        },
    )
    sid = res["sid"]
    for _ in range(120):
        _, job = req(f"/services/search/jobs/{sid}", params={"output_mode": "json"})
        state = job["entry"][0]["content"]["dispatchState"]
        if state == "DONE":
            break
        if state in {"FAILED", "INTERNAL_CANCEL"}:
            raise RuntimeError(f"search failed: {state}")
        time.sleep(2)
    _, results = req(
        f"/services/search/jobs/{sid}/results",
        params={"output_mode": "json", "count": str(count)},
    )
    return results.get("results", [])


def get_all(endpoint: str) -> list[dict[str, Any]]:
    _, res = req(endpoint, params={"output_mode": "json", "count": "0"})
    return res if isinstance(res, list) else []


def configure_entities() -> None:
    rows = run_search(
        '''index=os sourcetype="hardware_events" [ search index=rur_apps | fields host ]
| dedup hostname
| rename hostname as Entity_Title, entity_description AS description
| table Entity_Title, description, platform_type, cpu_model, cpu_cores, disk_drives, region'''
    )
    existing = {e["title"]: e for e in get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/entity")}
    updates: list[dict[str, Any]] = []
    creates: list[dict[str, Any]] = []

    for row in rows:
        title = row["Entity_Title"]
        info_fields = ["description", "platform_type", "cpu_model", "cpu_cores", "disk_drives", "region"]
        info_values = [row.get(field, "") for field in info_fields]
        if title in existing:
            entity = existing[title]
            type_ids = list(entity.get("entity_type_ids") or [])
            if RUR_ET_KEY not in type_ids:
                type_ids.append(RUR_ET_KEY)
            updates.append(
                {
                    "_key": entity["_key"],
                    "entity_type_ids": type_ids,
                    "informational": {"fields": info_fields, "values": info_values},
                }
            )
        else:
            creates.append(
                {
                    "title": title,
                    "host": [title],
                    "entity_name": [title],
                    "itsi_entity_id": [title],
                    "entity_type_ids": [RUR_ET_KEY],
                    "identifier": {"fields": ["host"], "values": [title]},
                    "informational": {"fields": info_fields, "values": info_values},
                    "description": row.get("description", ""),
                    "sec_grp": SEC_GRP,
                }
            )

    if updates:
        status, res = req(
            "/servicesNS/nobody/SA-ITOA/itoa_interface/entity/bulk_update?is_partial_data=1",
            method="POST",
            json_body=updates,
        )
        RESULT.log("Update existing entities with Ruritania type", "OK" if status == 200 else f"HTTP {status}", str(res)[:200])

    if creates:
        status, res = req(
            "/servicesNS/nobody/SA-ITOA/itoa_interface/entity/bulk_update?is_partial_data=0",
            method="POST",
            json_body=creates,
        )
        RESULT.log("Create missing Ruritania entities", "OK" if status == 200 else f"HTTP {status}", str(res)[:200])

    RESULT.log("Entity configuration", "OK", f"{len(rows)} Ruritania hosts processed")


def ensure_service(title: str, description: str) -> str:
    services = get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/service")
    for service in services:
        if service.get("title") == title:
            return service["_key"]
    status, res = req(
        "/servicesNS/nobody/SA-ITOA/itoa_interface/service",
        method="POST",
        json_body={
            "title": title,
            "description": description,
            "disabled": False,
            "enabled": 1,
            "sec_grp": SEC_GRP,
        },
    )
    if status != 200:
        raise RuntimeError(f"failed to create service {title}: {status} {res}")
    return res["_key"]


def configure_services() -> dict[str, str]:
    service_keys: dict[str, str] = {}
    for spec in SERVICES:
        key = ensure_service(spec["title"], spec["description"])
        service_keys[spec["title"]] = key

    for spec in SERVICES:
        key = service_keys[spec["title"]]
        depends = []
        for dep_title in spec["depends_on"]:
            depends.append({"_key": service_keys[dep_title], "title": dep_title})
        update: dict[str, Any] = {
            "_key": key,
            "title": spec["title"],
            "disabled": False,
            "enabled": 1,
            "depends_on": depends,
        }
        if spec["host_prefix"]:
            update["entity_rules"] = [
                {
                    "field": "entity_type_ids",
                    "rule_type": "matches",
                    "value": RUR_ET_KEY,
                    "multi_value": False,
                },
                {
                    "field": "title",
                    "rule_type": "matches",
                    "value": f"{spec['host_prefix']}*",
                    "multi_value": False,
                },
            ]
            status, _ = req(
                f"/servicesNS/nobody/SA-ITOA/itoa_interface/service/{key}/base_service_template",
                method="POST",
                json_body={"_key": NIX_TEMPLATE},
            )
            RESULT.log(f"Link nix template to {spec['title']}", "OK" if status == 200 else f"HTTP {status}")

        status, res = req(
            "/servicesNS/nobody/SA-ITOA/itoa_interface/service/bulk_update?is_partial_data=1",
            method="POST",
            json_body=[update],
        )
        RESULT.log(f"Configure service {spec['title']}", "OK" if status == 200 else f"HTTP {status}", str(res)[:120])

    return service_keys


def configure_custom_kpis(service_keys: dict[str, str]) -> None:
    for service_title, kpi_title, search, threshold_field in CUSTOM_KPIS:
        service_key = service_keys[service_title]
        status, res = req(
            "/servicesNS/nobody/SA-ITOA/itoa_interface/kpi",
            method="POST",
            json_body={
                "title": kpi_title,
                "description": f"Custom latency KPI for {service_title}",
                "search": search,
                "base_search": search,
                "search_alert": search,
                "threshold_field": threshold_field,
                "aggregate_thresholds": LATENCY_THRESHOLDS,
                "entity_thresholds": LATENCY_THRESHOLDS,
                "backfill_enabled": True,
                "backfill_earliest_time": "-1d",
                "gap_severity": "normal",
                "unit": "ms",
                "aggregate_statop": "avg",
                "entity_statop": "avg",
                "search_type": "adhoc",
                "urgency": "5",
                "alert_period": "15",
                "alert_on": "both",
                "search_alert": search,
                "search_alert_earliest": "15",
                "is_entity_breakdown": True,
                "entity_id_fields": "host",
                "entity_breakdown_id_fields": "host",
                "service_id": service_key,
                "enabled": True,
            },
        )
        RESULT.log(f"Add KPI {kpi_title}", "OK" if status == 200 else f"HTTP {status}", str(res)[:200])


def configure_event_management() -> None:
    for name in {
        "Service Monitoring - KPI Degraded",
        "Service Monitoring - Sustained KPI Degradation (Recommended)",
    }:
        status, _ = req(
            f"/servicesNS/nobody/SA-ITOA/saved/searches/{urllib.parse.quote(name)}",
            method="POST",
            data={"disabled": "0"},
        )
        RESULT.log(f"Enable correlation search: {name}", "OK" if status == 200 else f"HTTP {status}")

    _, saved = req("/servicesNS/nobody/SA-ITOA/saved/searches", params={"output_mode": "json", "count": "0"})
    existing = {entry["name"] for entry in saved.get("entry", [])}
    if "Ruritania Application Errors" not in existing:
        status, res = req(
            "/servicesNS/nobody/SA-ITOA/saved/searches",
            method="POST",
            data={
                "name": "Ruritania Application Errors",
                "description": "Detect HTTP/error events in Ruritania application logs",
                "search": '''index=rur_apps (status>=400 OR isnotnull(error))
| eval service_name=case(
    like(host, "api%"), "API Server",
    like(host, "app%"), "App Server",
    like(host, "login%"), "Login Server",
    like(host, "db%"), "Database Server",
    true(), "Unknown Service")''',
                "disabled": "0",
                "is_scheduled": "1",
                "cron_schedule": "*/5 * * * *",
                "dispatch.earliest_time": "-5m",
                "dispatch.latest_time": "now",
                "action.itsi_event_generator": "1",
                "action.itsi_event_generator.param.severity": "high",
                "action.itsi_event_generator.param.title": "Ruritania Application Error on $host$",
            },
        )
        RESULT.log(
            "Create Ruritania Application Errors correlation search",
            "OK" if status in {200, 201} else f"HTTP {status}",
            str(res)[:200],
        )
    else:
        status, res = req(
            "/servicesNS/nobody/SA-ITOA/saved/searches/Ruritania%20Application%20Errors",
            method="POST",
            data={
                "search": '''index=rur_apps (status>=400 OR isnotnull(error))
| eval service_name=case(
    like(host, "api%"), "API Server",
    like(host, "app%"), "App Server",
    like(host, "login%"), "Login Server",
    like(host, "db%"), "Database Server",
    true(), "Unknown Service")''',
                "disabled": "0",
                "action.itsi_event_generator": "1",
                "action.itsi_event_generator.param.severity": "high",
                "action.itsi_event_generator.param.title": "Ruritania Application Error on $host$",
            },
        )
        RESULT.log(
            "Update Ruritania Application Errors correlation search",
            "OK" if status == 200 else f"HTTP {status}",
            str(res)[:200],
        )

    policies = get_all("/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy")
    for policy in policies:
        title = policy.get("title")
        if title in {"Episodes by Src", "Episodes by ITSI Service"}:
            key = policy["_key"]
            policy["disabled"] = 0
            status, _ = req(
                f"/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy/{key}",
                method="POST",
                json_body=policy,
            )
            RESULT.log(f"Enable aggregation policy: {title}", "OK" if status == 200 else f"HTTP {status}")


def audit() -> dict[str, Any]:
    services = get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/service")
    entities = get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/entity")
    corr = get_all("/servicesNS/nobody/SA-ITOA/event_management_interface/correlation_search")
    policies = get_all("/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy")
    glass = get_all("/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table")

    rur_entities = [e for e in entities if RUR_ET_KEY in (e.get("entity_type_ids") or [])]
    rur_services = [
        s
        for s in services
        if s.get("title") in {spec["title"] for spec in SERVICES}
    ]

    return {
        "services": [
            {
                "title": s.get("title"),
                "enabled": s.get("enabled"),
                "kpi_count": len(s.get("kpis") or []),
                "depends_on": [d.get("title") for d in (s.get("depends_on") or [])],
            }
            for s in rur_services
        ],
        "entity_total": len(entities),
        "ruritania_entities": len(rur_entities),
        "enabled_correlation_searches": [
            c.get("name") or c.get("title")
            for c in corr
            if not c.get("disabled") and (c.get("name") or c.get("title"))
        ],
        "enabled_aggregation_policies": [
            p.get("title") for p in policies if not p.get("disabled")
        ],
        "glass_tables": [g.get("title") for g in glass],
    }


def main() -> None:
    configure_entities()
    service_keys = configure_services()
    configure_custom_kpis(service_keys)
    configure_event_management()
    summary = audit()
    output = {"steps": RESULT.steps, "errors": RESULT.errors, "audit": summary}
    print("\n=== AUDIT SUMMARY ===")
    print(json.dumps(summary, indent=2))
    with open("lab_configuration_results.json", "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
    print("\nWrote lab_configuration_results.json")


if __name__ == "__main__":
    main()
