"""
cloud_logs_tools.py — IBM Cloud Logs ADK Tools
================================================
These tools let watsonx Orchestrate agents search, tail, and analyze
logs from IBM Cloud Logs (the next-gen logging service that replaced
IBM Log Analysis).

Available tools:
  1. list_log_instances    — List all Cloud Logs instances
  2. search_logs           — Search logs using Lucene-style queries
  3. get_recent_logs       — Get the N most recent log lines
  4. get_logs_by_severity  — Filter logs by severity (INFO, WARN, ERROR, CRITICAL)
  5. count_errors          — Count error/critical logs in a time window
  6. get_log_alerts        — List configured log alerts
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


def _get_logs_instances() -> list:
    """Internal helper: fetch all Cloud Logs instances via Resource Controller."""
    rc_url = "https://resource-controller.cloud.ibm.com/v2/resource_instances"
    params = {
        "resource_plan_id": "logs",  # Cloud Logs plan ID
        "limit": 100,
    }
    response = requests.get(rc_url, headers=auth_headers(), params=params, timeout=30)
    if response.status_code != 200:
        return []
    return response.json().get("resources", [])


def _logs_api_url(instance_guid: str) -> str:
    """Build the Cloud Logs API base URL for an instance."""
    return f"https://{instance_guid}.api.{REGION}.logs.cloud.ibm.com/v1"


# =============================================================================
# TOOL 1 — List Cloud Logs Instances
# =============================================================================

def list_log_instances() -> dict:
    """
    List all IBM Cloud Logs instances in your account.

    Returns a list of instances with their IDs (GUIDs) and names.
    You'll need the instance GUID to call other log tools.

    Parameters
    ----------
    None

    Returns
    -------
    dict
        {
          "instances": [
            {"guid": "abc-123", "name": "my-logs", "region": "us-south", "state": "active"},
            ...
          ]
        }
    """
    rc_url = "https://resource-controller.cloud.ibm.com/v2/resource_instances"

    # Cloud Logs resource type identifier
    params = {"resource_id": "logs", "limit": 50}
    response = requests.get(rc_url, headers=auth_headers(), params=params, timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list log instances: {response.status_code} — {response.text}"}

    resources = response.json().get("resources", [])
    instances = [
        {
            "guid": r.get("guid"),
            "name": r.get("name"),
            "id": r.get("id"),
            "region": r.get("region_id"),
            "state": r.get("state"),
            "created_at": r.get("created_at"),
        }
        for r in resources
    ]

    return {"instances": instances, "count": len(instances)}


# =============================================================================
# TOOL 2 — Search Logs
# =============================================================================

def search_logs(
    instance_guid: str,
    query: str,
    start_time_minutes_ago: int = 60,
    limit: int = 50,
    severity: str = None,
) -> dict:
    """
    Search logs in an IBM Cloud Logs instance using a text query.

    Parameters
    ----------
    instance_guid : str
        The GUID of the Cloud Logs instance. Get from list_log_instances().
    query : str
        Text to search for in log lines.
        Examples:
          - "error"                     (find logs containing 'error')
          - "NullPointerException"      (find specific exceptions)
          - "app_name:my-app error"     (scoped to an app)
    start_time_minutes_ago : int
        How far back to search, in minutes. Default: 60 (last 1 hour).
        Use 1440 for last 24 hours, 10080 for last week.
    limit : int
        Maximum number of log lines to return. Default: 50, max: 500.
    severity : str, optional
        Filter by severity. One of: "debug", "info", "warning", "error", "critical".

    Returns
    -------
    dict
        {
          "logs": [
            {
              "timestamp": "2024-01-15T10:23:45Z",
              "severity": "error",
              "text": "Connection timeout to database...",
              "application": "my-app",
              "subsystem": "backend"
            },
            ...
          ],
          "count": 12,
          "query": "error",
          "time_range_minutes": 60
        }
    """
    if not instance_guid or not query:
        return {"error": "instance_guid and query are required."}

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=start_time_minutes_ago)

    api_url = _logs_api_url(instance_guid)
    payload = {
        "query": query,
        "metadata": {
            "start_date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "limit": min(limit, 500),
    }

    if severity:
        payload["severity"] = severity

    response = requests.post(
        f"{api_url}/logs/query",
        headers=auth_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:
        return {
            "error": f"Log search failed: {response.status_code} — {response.text}",
            "tip": "Make sure instance_guid is correct and the instance is in the right region.",
        }

    data = response.json()
    logs = []
    for entry in data.get("results", []):
        logs.append({
            "timestamp": entry.get("timestamp"),
            "severity": entry.get("severity"),
            "text": entry.get("text", entry.get("log_line", "")),
            "application": entry.get("applicationName"),
            "subsystem": entry.get("subsystemName"),
        })

    return {
        "logs": logs,
        "count": len(logs),
        "query": query,
        "time_range_minutes": start_time_minutes_ago,
    }


# =============================================================================
# TOOL 3 — Get Recent Logs
# =============================================================================

def get_recent_logs(
    instance_guid: str,
    minutes_ago: int = 15,
    limit: int = 100,
) -> dict:
    """
    Retrieve the most recent log entries from a Cloud Logs instance.

    Parameters
    ----------
    instance_guid : str
        The GUID of the Cloud Logs instance.
    minutes_ago : int
        How far back to look. Default: 15 minutes.
    limit : int
        Number of log lines to return. Default: 100.

    Returns
    -------
    dict
        Most recent log lines sorted by time (newest first).
    """
    return search_logs(
        instance_guid=instance_guid,
        query="*",  # match everything
        start_time_minutes_ago=minutes_ago,
        limit=limit,
    )


# =============================================================================
# TOOL 4 — Get Logs by Severity
# =============================================================================

def get_logs_by_severity(
    instance_guid: str,
    severity: str,
    start_time_minutes_ago: int = 60,
    limit: int = 100,
) -> dict:
    """
    Retrieve logs filtered to a specific severity level.

    Parameters
    ----------
    instance_guid : str
        The GUID of the Cloud Logs instance.
    severity : str
        One of: "debug", "info", "warning", "error", "critical"
    start_time_minutes_ago : int
        Time window to search. Default: 60 minutes.
    limit : int
        Max results. Default: 100.

    Returns
    -------
    dict
        Log entries matching the requested severity level.

    Examples
    --------
    Get all errors in the last 2 hours:
        get_logs_by_severity("abc-123", "error", start_time_minutes_ago=120)

    Get critical alerts today:
        get_logs_by_severity("abc-123", "critical", start_time_minutes_ago=1440)
    """
    valid_severities = ["debug", "info", "warning", "error", "critical"]
    if severity.lower() not in valid_severities:
        return {
            "error": f"Invalid severity '{severity}'. Must be one of: {', '.join(valid_severities)}"
        }

    return search_logs(
        instance_guid=instance_guid,
        query="*",
        start_time_minutes_ago=start_time_minutes_ago,
        limit=limit,
        severity=severity.lower(),
    )


# =============================================================================
# TOOL 5 — Count Errors
# =============================================================================

def count_errors(instance_guid: str, start_time_minutes_ago: int = 60) -> dict:
    """
    Count error and critical log entries in a time window.

    Useful for quickly checking the health of your services without
    having to scroll through individual log lines.

    Parameters
    ----------
    instance_guid : str
        The GUID of the Cloud Logs instance.
    start_time_minutes_ago : int
        Time window. Default: 60 minutes (last hour).

    Returns
    -------
    dict
        {
          "time_window_minutes": 60,
          "error_count": 42,
          "critical_count": 3,
          "total_issues": 45,
          "health_status": "degraded"   # "healthy", "degraded", or "critical"
        }
    """
    if not instance_guid:
        return {"error": "instance_guid is required."}

    error_result = search_logs(instance_guid, "*", start_time_minutes_ago, 500, "error")
    critical_result = search_logs(instance_guid, "*", start_time_minutes_ago, 500, "critical")

    if "error" in error_result:
        return error_result

    error_count = error_result.get("count", 0)
    critical_count = critical_result.get("count", 0)
    total = error_count + critical_count

    if total == 0:
        health = "healthy"
    elif critical_count > 0 or error_count > 50:
        health = "critical"
    else:
        health = "degraded"

    return {
        "time_window_minutes": start_time_minutes_ago,
        "error_count": error_count,
        "critical_count": critical_count,
        "total_issues": total,
        "health_status": health,
        "recommendation": {
            "healthy": "No issues detected.",
            "degraded": f"Found {error_count} errors. Review logs for root cause.",
            "critical": f"URGENT: {critical_count} critical events! Immediate attention needed.",
        }.get(health),
    }


# =============================================================================
# TOOL 6 — Get Log Alerts
# =============================================================================

def get_log_alerts(instance_guid: str) -> dict:
    """
    List all configured alerting rules for a Cloud Logs instance.

    Parameters
    ----------
    instance_guid : str
        The GUID of the Cloud Logs instance.

    Returns
    -------
    dict
        List of alert rules with their names, conditions, and notification channels.
    """
    if not instance_guid:
        return {"error": "instance_guid is required."}

    api_url = _logs_api_url(instance_guid)
    response = requests.get(
        f"{api_url}/alerts",
        headers=auth_headers(),
        timeout=30,
    )

    if response.status_code != 200:
        return {"error": f"Failed to get alerts: {response.status_code} — {response.text}"}

    alerts = response.json().get("alerts", [])
    formatted = [
        {
            "name": a.get("name"),
            "enabled": a.get("is_active", True),
            "severity": a.get("severity"),
            "condition_type": a.get("condition", {}).get("type"),
            "notification_groups": len(a.get("notification_groups", [])),
        }
        for a in alerts
    ]

    return {"alerts": formatted, "count": len(formatted)}


# =============================================================================
# ADK Registration
# =============================================================================

CLOUD_LOGS_TOOLS = [
    {
        "name": "list_log_instances",
        "description": "List all IBM Cloud Logs instances in your account.",
        "function": list_log_instances,
        "parameters": {},
    },
    {
        "name": "search_logs",
        "description": "Search log entries using a text query.",
        "function": search_logs,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Cloud Logs instance GUID."},
            "query": {"type": "string", "description": "Search text (e.g. 'error', 'timeout')."},
            "start_time_minutes_ago": {"type": "integer", "description": "How far back to search in minutes. Default 60."},
            "limit": {"type": "integer", "description": "Max results. Default 50."},
            "severity": {"type": "string", "description": "Optional: debug, info, warning, error, critical."},
        },
    },
    {
        "name": "get_recent_logs",
        "description": "Get the most recent log lines from a Cloud Logs instance.",
        "function": get_recent_logs,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Cloud Logs instance GUID."},
            "minutes_ago": {"type": "integer", "description": "How far back to look. Default 15."},
            "limit": {"type": "integer", "description": "Number of lines. Default 100."},
        },
    },
    {
        "name": "get_logs_by_severity",
        "description": "Get logs filtered by severity level (error, critical, warning, etc.).",
        "function": get_logs_by_severity,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Cloud Logs instance GUID."},
            "severity": {"type": "string", "description": "Severity: debug, info, warning, error, critical."},
            "start_time_minutes_ago": {"type": "integer", "description": "Time window. Default 60."},
            "limit": {"type": "integer", "description": "Max results. Default 100."},
        },
    },
    {
        "name": "count_errors",
        "description": "Count error and critical log events and get a health summary.",
        "function": count_errors,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Cloud Logs instance GUID."},
            "start_time_minutes_ago": {"type": "integer", "description": "Time window. Default 60."},
        },
    },
    {
        "name": "get_log_alerts",
        "description": "List all configured alerting rules for a Cloud Logs instance.",
        "function": get_log_alerts,
        "parameters": {
            "instance_guid": {"type": "string", "description": "Cloud Logs instance GUID."},
        },
    },
]

if __name__ == "__main__":
    print("Testing Cloud Logs Tools...")
    result = list_log_instances()
    print(json.dumps(result, indent=2))
