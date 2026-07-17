"""Load Splunk Show credentials from env vars or a local credentials.csv (gitignored)."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from urllib.parse import urlparse


def load_splunk_config() -> tuple[str, str, str]:
    """Return (host, username, password) for Splunk REST on port 8089."""
    env_host = os.environ.get("SPLUNK_HOST", "").strip()
    env_user = os.environ.get("SPLUNK_USER", "").strip()
    env_pass = os.environ.get("SPLUNK_PASSWORD", "").strip()

    if env_host and env_user and env_pass:
        host = env_host.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        return host, env_user, env_pass

    creds_path = Path(__file__).parent / "credentials.csv"
    if creds_path.exists():
        candidates = [creds_path]
    else:
        candidates = sorted(Path(__file__).parent.glob("splunk-it-service-intelligence*.csv"))
    if candidates:
        with candidates[-1].open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise SystemExit(f"{candidates[-1].name} is empty")
        row = rows[-1]
        url = row.get("url", "")
        host = urlparse(url).hostname or url.replace("https://", "").replace("http://", "").split("/")[0]
        user = row.get("adminUsername") or row.get("adminusername") or row.get("username")
        password = row.get("adminPassword") or row.get("adminpassword") or row.get("password")
        if not all([host, user, password]):
            raise SystemExit("credentials.csv must include adminUsername, adminPassword, and url")
        return host, user, password

    raise SystemExit(
        "Splunk credentials not found. Either:\n"
        "  1. Copy credentials.example.csv to credentials.csv and fill in values, or\n"
        "  2. Export SPLUNK_HOST, SPLUNK_USER, SPLUNK_PASSWORD"
    )
