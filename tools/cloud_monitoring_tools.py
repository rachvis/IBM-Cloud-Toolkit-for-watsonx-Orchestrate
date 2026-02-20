"""
cloud_monitoring_tools.py — IBM Cloud Monitoring ADK Tools
===========================================================
These tools let watsonx Orchestrate agents query metrics, inspect
dashboards, and manage alerts from IBM Cloud Monitoring (powered
by Sysdig).

IBM Cloud Monitoring collects:
  - Infrastructure metrics (CPU, memory, disk, network)
  - Application metrics (custom metrics you push)
  - Kubernetes/container metrics
  - Platform metrics from IBM Cloud services

Available tools:
  1. list_monitoring_instances   — Find your monitoring instances
  2. query_metric                — Query a metric (CPU, memory, etc.)
  3. get_platform_metrics        — Get IBM platform service metrics
  4. list_alerts                 — List configured alerts
  5. get_alert_events            — Get recent alert firings
  6. get_team_dashboards         — List available dashboards
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, get_region

load_dotenv()

REGION = get_region()


def _monitoring_url(instance_guid: str) -> str:
    """Build Sysdig-compatible monitoring API URL."""
    return f"https://{REGION}.monitoring.cloud.ibm.com"


# =============================================================================
# TOOL 1 — List Monitoring Instances
# =============================================================================

def list_monitoring_instances() -> dict:
    """
    List all IBM Cloud Monitoring instances in your account.

    Returns instance GUIDs and names. Use the GUID in other monitoring tools.

    Parameters
    ----------
    None

    Returns
    -------
    dict
        {
          "instances": [
            {"guid": "abc-123", "name": "my-monitoring", "region": "us-south"},
            ...
          ]
        }
    """
    rc_url = "https://resource-controller.cloud.ibm.com/v2/resource_instances"
    params = {"resource_id": "sysdig-monitor", "limit": 50}
    response = requests.get(rc_url, headers=auth_headers(), params=params, timeout=30)

    if response.status_code != 200:
        return {
            "error": f"Failed to list monitoring instances: {response.status_code} — {response.text}"
        }

    resources = response.json().get("resources", [])
    instances = [
        {
            "guid": r.get("guid"),
            "name": r.get("name"),
            "region": r.get("region_id"),
            "state": r.get("state"),
            "id": r.get("id"),
            "dashboard_url": f"https://{r.get('region_id', REGION)}.monitoring.cloud.ibm.com",
        }
        for r in resources
    ]

    return {"instances": instances, "count": len(instances)}


# =============================================================================
# TOOL 2 — Query a Metric
# =============================================================================

def query_metric(
    instance_guid: str,
    metric_name: str,
    aggregation: str = "avg",
    start_time_minutes_ago: int = 60,
    segment_by: str = None,
) -> dict:
    """
    Query a specific metric from IBM Cloud Monitoring.

    Parameters
    ----------
    instance_guid : str
        The monitoring instance GUID from list_monitoring_instances().
    metric_name : str
        The metric to query. Common examples:
          - "cpu.used.percent"              CPU usage %
          - "memory.used.percent"           Memory usage %
          - "net.bytes.in"                  Network bytes in
          - "net.bytes.out"                 Network bytes out
          - "fs.used.percent"               Disk usage %
          - "container.cpu.used.percent"    Container CPU
          - "k8s.pod.cpu.used.percent"      Kubernetes pod CPU
    aggregation : str
        How to aggregate data points. One of:
          - "avg"   — average (default, good for most metrics)
          - "max"   — maximum (useful for spike detection)
          - "min"   — minimum
          - "sum"   — total (useful for counters like bytes)
          - "rate"  — rate of change per second
    start_time_minutes_ago : int
        How far back to query. Default: 60 minutes.
    segment_by : str, optional
        Dimension to break results down by.
        Examples: "host.hostName", "container.name", "k8s.pod.name"

    Returns
    -------
    dict
        {
          "metric": "cpu.used.percent",
          "aggregation": "avg",
          "data_points": [
            {"timestamp": "2024-01-15T10:00:00Z", "value": 23.4},
            ...
          ],
          "summary": {"current": 23.4, "average": 18.2, "max": 45.1, "min": 5.3}
        }
    """
    if not instance_guid or not metric_name:
        return {"error": "instance_guid and metric_name are required."}

    now = int(time.time())
    start = now - (start_time_minutes_ago * 60)

    base_url = _monitoring_url(instance_guid)
    payload = {
        "start": start,
        "end": now,
        "last": start_time_minutes_ago * 60,
        "sampling": max(60, (start_time_minutes_ago * 60) // 100),  # auto-granularity
        "metrics": [
            {
                "id": metric_name,
                "aggregations": {"time": aggregation, "group": aggregation},
            }
        ],
    }

    if segment_by:
        payload["metrics"].append({"id": segment_by})

    headers = {**auth_headers(), "IBMInstanceID": instance_guid}
    response = requests.post(
        f"{base_url}/api/data/metrics",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:
        return {
            "error": f"Metric query failed: {response.status_code} — {response.text}",
            "tip": "Verify the metric name. Use IBM Cloud docs for valid metric names.",
        }

    data = response.json()
    data_points = []
    values = []

    for sample in data.get("data", []):
        ts = datetime.fromtimestamp(sample.get("t", 0), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        val = sample.get("d", [None])[0]
        data_points.append({"timestamp": ts, "value": val})
        if val is not None:
            values.append(val)

    summary = {}
    if values:
        summary = {
            "current": round(values[-1], 4),
            "average": round(sum(values) / len(values), 4),
            "max": round(max(values), 4),
            "min": round(min(values), 4),
        }

    return {
        "metric": metric_name,
        "aggregation": aggregation,
        "time_range_minutes": start_time_minutes_ago,
        "data_points": data_points,
        "summary": summary,
    }


# =============================================================================
# TOOL 3 — Get Platform Metrics (IBM services like Code Engine, ROKS, etc.)
# =============================================================================

def get_platform_metrics(
    instance_guid: str,
    service_name: str,
    metric_name: str,
    start_time_minutes_ago: int = 30,
) -> dict:
    """
    Query platform metrics emitted by IBM Cloud services.

    IBM Cloud services automatically push metrics to monitoring. This tool
    lets you query those metrics for a specific IBM Cloud service.

    Parameters
    ----------
    instance_guid : str
        The monitoring instance GUID.
    service_name : str
        The IBM Cloud service name. Examples:
          - "codeengine"         IBM Code Engine
          - "databases-for-postgresql"
          - "cloud-object-storage"
          - "event-streams"
    metric_name : str
        The platform metric to query. Examples for Code Engine:
          - "ibm_codeengine_app_instances"
          - "ibm_codeengine_app_cpu_usage"
          - "ibm_codeengine_app_memory_usage"
    start_time_minutes_ago : int
        Time window. Default: 30 minutes.

    Returns
    -------
    dict
        Metric data points and summary statistics.
    """
    # Platform metrics follow the ibm_<service>_<metric> naming pattern
    full_metric = metric_name if metric_name.startswith("ibm_") else f"ibm_{service_name}_{metric_name}"

    return query_metric(
        instance_guid=instance_guid,
        metric_name=full_metric,
        aggregation="avg",
        start_time_minutes_ago=start_time_minutes_ago,
        segment_by="ibm_service_name",
    )


# =============================================================================
# TOOL 4 — List Alerts
# =============================================================================

def list_alerts(instance_guid: str) -> dict:
    """
    List all configured monitoring alerts for an IBM Cloud Monitoring instance.

    Parameters
    ----------
    instance_guid : str
        The monitoring instance GUID.

    Returns
    -------
    dict
        {
          "alerts": [
            {
              "id": 123,
              "name": "High CPU Alert",
              "enabled": true,
              "severity": "high",
              "condition": "cpu.used.percent > 80",
              "notification_channels": ["email", "slack"]
            }
          ]
        }
    """
    if not instance_guid:
        return {"error": "instance_guid is required."}

    base_url = _monitoring_url(instance_guid)
    headers = {**auth_headers(), "IBMInstanceID": instance_guid}

    response = requests.get(
        f"{base_url}/api/alerts",
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        return {"error": f"Failed to list alerts: {response.status_code} — {response.text}"}

    data = response.json()
    alerts = [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "enabled": a.get("enabled", True),
            "severity": a.get("severity"),
            "type": a.get("type"),
            "condition": a.get("condition"),
            "notification_channels": [nc.get("type") for nc in a.get("notificationChannels", [])],
        }
        for a in data.get("alerts", [])
    ]

    return {"alerts": alerts, "count": len(alerts)}


# =============================================================================
# TOOL 5 — Get Alert Events (recent firings)
# =============================================================================

def get_alert_events(
    instance_guid: str,
    start_time_minutes_ago: int = 60,
    status: str = "triggered",
) -> dict:
    """
    Get recent alert firing events from IBM Cloud Monitoring.

    Parameters
    ----------
    instance_guid : str
        The monitoring instance GUID.
    start_time_minutes_ago : int
        Look back this many minutes. Default: 60.
    status : str
        Alert status to filter by. One of:
          - "triggered"  — currently firing alerts (default)
          - "resolved"   — recently resolved
          - "acknowledged" — acknowledged by someone

    Returns
    -------
    dict
        Recent alert events with timestamps and severities.
    """
    if not instance_guid:
        return {"error": "instance_guid is required."}

    now = int(time.time())
    start = now - (start_time_minutes_ago * 60)

    base_url = _monitoring_url(instance_guid)
    headers = {**auth_headers(), "IBMInstanceID": instance_guid}

    params = {
        "from": start * 1_000_000,  # microseconds
        "to": now * 1_000_000,
        "status": status,
        "limit": 100,
    }

    response = requests.get(
        f"{base_url}/api/v2/events",
        headers=headers,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        return {"error": f"Failed to get alert events: {response.status_code} — {response.text}"}

    data = response.json()
    events = []
    for e in data.get("events", []):
        ts = datetime.fromtimestamp(
            e.get("timestamp", 0) / 1_000_000, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        events.append({
            "timestamp": ts,
            "name": e.get("name"),
            "severity": e.get("severity"),
            "status": e.get("status"),
            "description": e.get("description"),
        })

    return {
        "events": events,
        "count": len(events),
        "status_filter": status,
        "time_window_minutes": start_time_minutes_ago,
    }


# =============================================================================
# TOOL 6 — Get Team Dashboards
# =============================================================================

def get_team_dashboards(instance_guid: str) -> dict:
    """
    List all monitoring dashboards available in a Cloud Monitoring instance.

    Parameters
    ----------
    instance_guid : str
        The monitoring instance GUID.

    Returns
    -------
    dict
        List of dashboards with names and IDs. Use IDs to deep-link.
    """
    if not instance_guid:
        return {"error": "instance_guid is required."}

    base_url = _monitoring_url(instance_guid)
    headers = {**auth_headers(), "IBMInstanceID": instance_guid}

    response = requests.get(
        f"{base_url}/api/v3/dashboards",
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        return {"error": f"Failed to get dashboards: {response.status_code} — {response.text}"}

    data = response.json()
    dashboards = [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "description": d.get("description"),
            "created_by": d.get("createdByName"),
            "panel_count": len(d.get("panels", [])),
            "url": f"{base_url}/#/dashboard/{d.get('id')}",
        }
        for d in data.get("dashboards", [])
    ]

    return {"dashboards": dashboards, "count": len(dashboards)}


# =============================================================================
# ADK Registration
# =============================================================================

MONITORING_TOOLS = [
    {
        "name": "list_monitoring_instances",
        "description": "List all IBM Cloud Monitoring instances in the account.",
        "function": list_monitoring_instances,
        "parameters": {},
    },
    {
        "name": "query_metric",
        "description": "Query a specific metric (CPU, memory, network, etc.) from IBM Cloud Monitoring.",
        "function": query_metric,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Monitoring instance GUID."},
            "metric_name": {"type": "string", "description": "Metric ID (e.g. 'cpu.used.percent')."},
            "aggregation": {"type": "string", "description": "avg, max, min, sum, or rate. Default avg."},
            "start_time_minutes_ago": {"type": "integer", "description": "Time window in minutes. Default 60."},
            "segment_by": {"type": "string", "description": "Optional dimension (e.g. 'host.hostName')."},
        },
    },
    {
        "name": "get_platform_metrics",
        "description": "Get metrics emitted by IBM Cloud platform services like Code Engine or Databases.",
        "function": get_platform_metrics,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Monitoring instance GUID."},
            "service_name": {"type": "string", "description": "IBM service name (e.g. 'codeengine')."},
            "metric_name": {"type": "string", "description": "Metric name."},
            "start_time_minutes_ago": {"type": "integer", "description": "Time window. Default 30."},
        },
    },
    {
        "name": "list_alerts",
        "description": "List all configured monitoring alert rules.",
        "function": list_alerts,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Monitoring instance GUID."},
        },
    },
    {
        "name": "get_alert_events",
        "description": "Get recent alert firing events from Cloud Monitoring.",
        "function": get_alert_events,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Monitoring instance GUID."},
            "start_time_minutes_ago": {"type": "integer", "description": "Time window. Default 60."},
            "status": {"type": "string", "description": "triggered, resolved, or acknowledged. Default triggered."},
        },
    },
    {
        "name": "get_team_dashboards",
        "description": "List all monitoring dashboards in a Cloud Monitoring instance.",
        "function": get_team_dashboards,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Monitoring instance GUID."},
        },
    },
]

if __name__ == "__main__":
    print("Testing Cloud Monitoring Tools...")
    result = list_monitoring_instances()
    print(json.dumps(result, indent=2))
