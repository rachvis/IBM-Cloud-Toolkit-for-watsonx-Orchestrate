"""
databases_tools.py — IBM Cloud Databases (ICD) ADK Tools
==========================================================
These tools let watsonx Orchestrate agents manage IBM Cloud Databases,
which provides managed database services including:

  - PostgreSQL     — Relational database
  - MySQL          — Popular open-source RDBMS
  - Redis          — In-memory cache/store
  - MongoDB        — Document database
  - Elasticsearch  — Search and analytics
  - etcd           — Key-value store for Kubernetes
  - RabbitMQ       — Message broker
  - EnterpriseDB   — Enterprise PostgreSQL

Available tools:
  1. list_database_instances    — List all ICD instances
  2. get_database_details       — Get details about one instance
  3. list_database_backups      — List available backups
  4. create_manual_backup       — Trigger a manual backup
  5. get_connection_strings     — Get connection info (no passwords)
  6. scale_database             — Change CPU/memory/disk allocation
  7. list_database_tasks        — Check ongoing operations
  8. get_database_whitelist     — Get IP whitelist rules
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, get_region

load_dotenv()

REGION = get_region()

# IBM Cloud Databases API v5
ICD_API = os.getenv(
    "IBM_DATABASES_API",
    f"https://api.{REGION}.databases.cloud.ibm.com/v5/ibm"
)


# =============================================================================
# TOOL 1 — List Database Instances
# =============================================================================

def list_database_instances(database_type: str = None) -> dict:
    """
    List all IBM Cloud Database instances in your account.

    Parameters
    ----------
    database_type : str, optional
        Filter by database type. Options:
          "postgresql", "mysql", "redis", "mongodb",
          "elasticsearch", "etcd", "rabbitmq", "enterprisedb"
        Leave empty to list ALL database instances.

    Returns
    -------
    dict
        {
          "databases": [
            {
              "id": "crn:v1:...",
              "name": "my-postgres",
              "type": "postgresql",
              "version": "14",
              "region": "us-south",
              "state": "running",
              "plan": "standard"
            },
            ...
          ]
        }
    """
    rc_url = "https://resource-controller.cloud.ibm.com/v2/resource_instances"

    # All ICD types share the same resource_id prefix
    db_resource_ids = {
        "postgresql": "databases-for-postgresql",
        "mysql": "databases-for-mysql",
        "redis": "databases-for-redis",
        "mongodb": "databases-for-mongodb",
        "elasticsearch": "databases-for-elasticsearch",
        "etcd": "databases-for-etcd",
        "rabbitmq": "messages-for-rabbitmq",
        "enterprisedb": "edb-se",
    }

    if database_type and database_type.lower() in db_resource_ids:
        resource_ids = [db_resource_ids[database_type.lower()]]
    else:
        resource_ids = list(db_resource_ids.values())

    all_instances = []
    for resource_id in resource_ids:
        params = {"resource_id": resource_id, "limit": 100}
        response = requests.get(rc_url, headers=auth_headers(), params=params, timeout=30)
        if response.status_code == 200:
            for r in response.json().get("resources", []):
                # Derive db type from resource plan
                crn = r.get("resource_id", "")
                db_type = next(
                    (k for k, v in db_resource_ids.items() if v in crn), "unknown"
                )
                all_instances.append({
                    "id": r.get("id"),   # This is the CRN — used in other tools
                    "guid": r.get("guid"),
                    "name": r.get("name"),
                    "type": db_type,
                    "region": r.get("region_id"),
                    "state": r.get("state"),
                    "plan": r.get("resource_plan_id", "").split(":")[-1],
                    "created_at": r.get("created_at"),
                    "dashboard_url": r.get("dashboard_url"),
                })

    return {
        "databases": all_instances,
        "count": len(all_instances),
        "filter": database_type or "all",
    }


# =============================================================================
# TOOL 2 — Get Database Details
# =============================================================================

def get_database_details(instance_id: str) -> dict:
    """
    Get detailed information about a specific IBM Cloud Database instance.

    Parameters
    ----------
    instance_id : str
        The CRN (Cloud Resource Name) or ID of the database instance.
        Get this from list_database_instances().
        Example: "crn:v1:bluemix:public:databases-for-postgresql:us-south:..."

    Returns
    -------
    dict
        Detailed instance info including version, storage, memory, connections,
        and current status.
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code == 404:
        return {"error": f"Database instance not found: {instance_id}"}
    if response.status_code != 200:
        return {"error": f"Failed to get database details: {response.status_code} — {response.text}"}

    d = response.json().get("deployment", {})

    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "type": d.get("type"),
        "version": d.get("version"),
        "platform_options": d.get("platform_options", {}),
        "location": d.get("location"),
        "tags": d.get("tags", []),
        "members": [
            {
                "role": m.get("role"),
                "count": m.get("count"),
                "memory_mb": m.get("memory_allocation_mb"),
                "disk_mb": m.get("disk_allocation_mb"),
                "cpu": m.get("cpu_allocation_count"),
            }
            for m in d.get("groups", [])
        ],
        "connection_draining": d.get("connection_draining", False),
        "auto_scaling": d.get("auto_scaling", {}),
    }


# =============================================================================
# TOOL 3 — List Database Backups
# =============================================================================

def list_database_backups(instance_id: str) -> dict:
    """
    List available backups for a database instance.

    IBM Cloud Databases automatically creates daily backups and
    retains them for 30 days. You can also create manual backups.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.

    Returns
    -------
    dict
        {
          "backups": [
            {
              "id": "backup-abc123",
              "type": "scheduled",        # or "manual"
              "status": "completed",
              "created_at": "2024-01-15T02:00:00Z",
              "is_restorable": true
            }
          ]
        }
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}/backups"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list backups: {response.status_code} — {response.text}"}

    backups = [
        {
            "id": b.get("id"),
            "type": b.get("type"),
            "status": b.get("status"),
            "created_at": b.get("created_at"),
            "is_restorable": b.get("is_restorable", False),
            "download_link": b.get("download_link"),
        }
        for b in response.json().get("backups", [])
    ]

    return {
        "backups": backups,
        "count": len(backups),
        "instance_id": instance_id,
    }


# =============================================================================
# TOOL 4 — Create Manual Backup
# =============================================================================

def create_manual_backup(instance_id: str) -> dict:
    """
    Trigger an immediate manual backup of a database instance.

    Manual backups are useful before performing maintenance operations,
    schema changes, or deploying major application updates.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.

    Returns
    -------
    dict
        {
          "success": true,
          "task_id": "task-abc123",
          "message": "Backup initiated. Check task status with list_database_tasks()."
        }
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}/backups"
    response = requests.post(url, headers=auth_headers(), json={}, timeout=30)

    if response.status_code in (200, 201, 202):
        data = response.json()
        task = data.get("task", {})
        return {
            "success": True,
            "task_id": task.get("id"),
            "status": task.get("status"),
            "message": "Manual backup initiated. Use list_database_tasks() to check progress.",
        }

    return {"error": f"Failed to create backup: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 5 — Get Connection Strings
# =============================================================================

def get_connection_strings(
    instance_id: str,
    user_type: str = "admin",
    endpoint_type: str = "public",
) -> dict:
    """
    Get connection information for a database instance.

    IMPORTANT: This returns connection details WITHOUT passwords for security.
    Passwords must be retrieved separately from IBM Secrets Manager or set
    when creating database users.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.
    user_type : str
        Type of user to get connection info for. Default: "admin".
        Other options depend on users you've created.
    endpoint_type : str
        "public" (default) — public internet endpoint
        "private" — private network endpoint (faster, more secure)

    Returns
    -------
    dict
        Connection details including hostname, port, and TLS certificate info.
        Does NOT include passwords.
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}/users/{user_type}/connections/{endpoint_type}"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {
            "error": f"Failed to get connections: {response.status_code} — {response.text}"
        }

    data = response.json().get("connection", {})

    # Extract the most useful connection info
    result = {
        "instance_id": instance_id,
        "user_type": user_type,
        "endpoint_type": endpoint_type,
    }

    # PostgreSQL/MySQL style
    if "postgres" in data or "cli" in data:
        db_conn = data.get("postgres", data.get("cli", {}))
        hosts = db_conn.get("composed", [])
        if hosts:
            result["connection_string_template"] = hosts[0].replace(
                "{username}", user_type
            ).replace("{password}", "YOUR_PASSWORD_HERE")

    # Common fields across all DB types
    for db_key in ["postgres", "mysql", "redis", "mongodb", "https", "amqps"]:
        if db_key in data:
            conn = data[db_key]
            hosts_list = conn.get("hosts", [])
            if hosts_list:
                result["hosts"] = hosts_list
                result["port"] = hosts_list[0].get("port")
                result["hostname"] = hosts_list[0].get("hostname")
            result["database"] = conn.get("database")
            result["tls_enabled"] = conn.get("ssl", False)
            result["certificate"] = {
                "name": conn.get("certificate", {}).get("name"),
                "note": "Download cert from IBM Cloud console → your database → Overview → TLS Certificate",
            }
            break

    result["security_note"] = (
        "Password not included for security. "
        "Use IBM Secrets Manager or reset via IBM Cloud console."
    )

    return result


# =============================================================================
# TOOL 6 — Scale Database
# =============================================================================

def scale_database(
    instance_id: str,
    group_id: str = "member",
    memory_mb: int = None,
    disk_mb: int = None,
    cpu_count: int = None,
) -> dict:
    """
    Scale a database instance's resources (memory, disk, CPU).

    Use this to increase capacity when your database is under load,
    or decrease to save costs during quiet periods.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.
    group_id : str
        The group to scale. Default: "member" (the main data group).
        Some databases also have "analytics" or "search" groups.
    memory_mb : int, optional
        New memory in MB. Must be a multiple of 128.
        Minimum varies by plan (usually 1024 MB).
        Example: 4096 for 4 GB.
    disk_mb : int, optional
        New disk in MB. Must be a multiple of 1024.
        Disk can only be increased, NOT decreased.
        Example: 20480 for 20 GB.
    cpu_count : int, optional
        Number of dedicated CPUs. Use 0 for shared CPU.
        Dedicated CPU is only available on certain plans.

    Returns
    -------
    dict
        Task details. Scale operations take a few minutes to complete.
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    if not any([memory_mb, disk_mb, cpu_count]):
        return {"error": "At least one of memory_mb, disk_mb, or cpu_count must be specified."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    payload = {"group": {}}
    if memory_mb:
        payload["group"]["memory"] = {"allocation_mb": memory_mb}
    if disk_mb:
        payload["group"]["disk"] = {"allocation_mb": disk_mb}
    if cpu_count is not None:
        payload["group"]["cpu"] = {"allocation_count": cpu_count}

    url = f"{ICD_API}/deployments/{encoded_id}/groups/{group_id}"
    response = requests.patch(url, headers=auth_headers(), json=payload, timeout=30)

    if response.status_code in (200, 201, 202):
        data = response.json()
        task = data.get("task", {})
        return {
            "success": True,
            "task_id": task.get("id"),
            "message": "Scaling operation started. This may take 5-15 minutes. Use list_database_tasks() to monitor.",
            "changes": {
                "memory_mb": memory_mb,
                "disk_mb": disk_mb,
                "cpu_count": cpu_count,
            },
        }

    return {"error": f"Failed to scale database: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 7 — List Database Tasks
# =============================================================================

def list_database_tasks(instance_id: str) -> dict:
    """
    List ongoing or recent tasks for a database instance.

    Use this to monitor the progress of backup, restore, or scaling operations.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.

    Returns
    -------
    dict
        List of recent tasks with their status and completion percentage.
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}/tasks"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list tasks: {response.status_code} — {response.text}"}

    tasks = [
        {
            "id": t.get("id"),
            "description": t.get("description"),
            "status": t.get("status"),
            "progress_percent": t.get("progress_percent"),
            "created_at": t.get("created_at"),
        }
        for t in response.json().get("tasks", [])
    ]

    return {"tasks": tasks, "count": len(tasks)}


# =============================================================================
# TOOL 8 — Get Database IP Whitelist
# =============================================================================

def get_database_whitelist(instance_id: str) -> dict:
    """
    Get the IP allowlist (whitelist) for a database instance.

    IBM Cloud Databases can restrict connections to specific IP ranges
    for additional security.

    Parameters
    ----------
    instance_id : str
        The CRN of the database instance.

    Returns
    -------
    dict
        List of allowed IP addresses/CIDRs and their descriptions.
    """
    if not instance_id:
        return {"error": "instance_id (CRN) is required."}

    import urllib.parse
    encoded_id = urllib.parse.quote(instance_id, safe="")

    url = f"{ICD_API}/deployments/{encoded_id}/whitelists/ip_addresses"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to get whitelist: {response.status_code} — {response.text}"}

    entries = response.json().get("ip_addresses", [])
    formatted = [
        {
            "address": e.get("address"),
            "description": e.get("description", "No description"),
        }
        for e in entries
    ]

    return {
        "whitelist": formatted,
        "count": len(formatted),
        "note": "Empty whitelist means ALL IP addresses are allowed (less secure).",
    }


# =============================================================================
# ADK Registration
# =============================================================================

DATABASES_TOOLS = [
    {
        "name": "list_database_instances",
        "description": "List all IBM Cloud Database instances (PostgreSQL, MySQL, Redis, MongoDB, etc.).",
        "function": list_database_instances,
        "parameters": {
            "database_type": {
                "type": "string",
                "description": "Optional filter: postgresql, mysql, redis, mongodb, elasticsearch, etcd, rabbitmq.",
            },
        },
    },
    {
        "name": "get_database_details",
        "description": "Get detailed info about an IBM Cloud Database instance.",
        "function": get_database_details,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN from list_database_instances()."},
        },
    },
    {
        "name": "list_database_backups",
        "description": "List available backups for a database instance.",
        "function": list_database_backups,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
        },
    },
    {
        "name": "create_manual_backup",
        "description": "Trigger an immediate manual backup of a database instance.",
        "function": create_manual_backup,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
        },
    },
    {
        "name": "get_connection_strings",
        "description": "Get connection details (hostname, port, TLS info) for a database instance. Does NOT return passwords.",
        "function": get_connection_strings,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
            "user_type": {"type": "string", "description": "User type. Default: admin."},
            "endpoint_type": {"type": "string", "description": "public or private. Default: public."},
        },
    },
    {
        "name": "scale_database",
        "description": "Scale a database instance's memory, disk, or CPU allocation.",
        "function": scale_database,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
            "group_id": {"type": "string", "description": "Group to scale. Default: member."},
            "memory_mb": {"type": "integer", "description": "New memory in MB (multiple of 128)."},
            "disk_mb": {"type": "integer", "description": "New disk in MB (multiple of 1024, can only increase)."},
            "cpu_count": {"type": "integer", "description": "Number of dedicated CPUs."},
        },
    },
    {
        "name": "list_database_tasks",
        "description": "List ongoing or recent database operations (backup, scale, restore).",
        "function": list_database_tasks,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
        },
    },
    {
        "name": "get_database_whitelist",
        "description": "Get the IP allowlist configured for a database instance.",
        "function": get_database_whitelist,
        "parameters": {
            "instance_id": {"type": "string", "description": "Database instance CRN."},
        },
    },
]

if __name__ == "__main__":
    print("Testing IBM Cloud Databases Tools...")
    result = list_database_instances()
    print(json.dumps(result, indent=2))
