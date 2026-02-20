"""
code_engine_tools.py — IBM Cloud Code Engine ADK Tools
=======================================================
These tools let watsonx Orchestrate agents manage IBM Cloud Code Engine,
which is IBM's serverless container platform.

What Code Engine does:
  - Run containerized apps without managing Kubernetes
  - Run batch jobs on demand
  - Auto-scales to zero when idle (cost-efficient)

Available tools in this file:
  1. list_code_engine_projects   — List all Code Engine projects
  2. list_code_engine_apps       — List apps in a project
  3. get_app_details             — Get details about one app
  4. create_app                  — Deploy a new app from a container image
  5. delete_app                  — Remove an app
  6. list_jobs                   — List batch jobs in a project
  7. create_job_run              — Trigger a batch job run
  8. get_job_run_status          — Check if a job run succeeded
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Add parent dir to path so we can import ibm_auth
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, get_region

load_dotenv()

# Base URL for Code Engine API v2
CE_API_BASE = os.getenv(
    "IBM_CODE_ENGINE_API",
    f"https://api.{get_region()}.codeengine.cloud.ibm.com/v2"
)


# =============================================================================
# TOOL 1 — List Code Engine Projects
# =============================================================================

def list_code_engine_projects() -> dict:
    """
    List all IBM Cloud Code Engine projects in your account.

    Returns a list of projects with their IDs, names, regions, and status.
    Use project IDs from this list as input to other Code Engine tools.

    Parameters
    ----------
    None

    Returns
    -------
    dict
        {
          "projects": [
            {"id": "abc123", "name": "my-project", "region": "us-south", "status": "active"},
            ...
          ],
          "count": 2
        }
    """
    url = f"{CE_API_BASE}/projects"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list projects: {response.status_code} — {response.text}"}

    data = response.json()
    projects = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "region": p.get("region"),
            "status": p.get("status"),
            "created_at": p.get("created_at"),
            "resource_group_id": p.get("resource_group_id"),
        }
        for p in data.get("projects", [])
    ]

    return {"projects": projects, "count": len(projects)}


# =============================================================================
# TOOL 2 — List Apps in a Project
# =============================================================================

def list_code_engine_apps(project_id: str) -> dict:
    """
    List all applications deployed in a Code Engine project.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project. Get this from list_code_engine_projects().

    Returns
    -------
    dict
        {
          "apps": [
            {
              "name": "my-app",
              "status": "ready",
              "image": "icr.io/my-namespace/my-image:latest",
              "url": "https://my-app.abc123.us-south.codeengine.appdomain.cloud",
              "instances": {"min": 0, "max": 10, "running": 2}
            },
            ...
          ]
        }
    """
    if not project_id:
        return {"error": "project_id is required. Use list_code_engine_projects() to find it."}

    url = f"{CE_API_BASE}/projects/{project_id}/apps"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list apps: {response.status_code} — {response.text}"}

    data = response.json()
    apps = [
        {
            "name": app.get("name"),
            "status": app.get("status"),
            "image": app.get("image_reference"),
            "url": app.get("endpoint"),
            "instances": {
                "min": app.get("scale_min_instances", 0),
                "max": app.get("scale_max_instances", 10),
            },
            "cpu": app.get("scale_cpu_limit"),
            "memory": app.get("scale_memory_limit"),
            "created_at": app.get("created_at"),
        }
        for app in data.get("apps", [])
    ]

    return {"apps": apps, "count": len(apps)}


# =============================================================================
# TOOL 3 — Get App Details
# =============================================================================

def get_app_details(project_id: str, app_name: str) -> dict:
    """
    Get detailed information about a specific Code Engine application.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.

    Returns
    -------
    dict
        Detailed app configuration including image, env vars, scaling, and endpoint.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}

    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code == 404:
        return {"error": f"App '{app_name}' not found in project '{project_id}'."}
    if response.status_code != 200:
        return {"error": f"Failed to get app: {response.status_code} — {response.text}"}

    app = response.json()
    return {
        "name": app.get("name"),
        "status": app.get("status"),
        "image": app.get("image_reference"),
        "url": app.get("endpoint"),
        "port": app.get("image_port", 8080),
        "env_vars": app.get("run_env_variables", []),
        "scaling": {
            "min_instances": app.get("scale_min_instances", 0),
            "max_instances": app.get("scale_max_instances", 10),
            "concurrency": app.get("scale_concurrency", 100),
            "cpu": app.get("scale_cpu_limit"),
            "memory": app.get("scale_memory_limit"),
        },
        "created_at": app.get("created_at"),
        "updated_at": app.get("updated_at"),
    }


# =============================================================================
# TOOL 4 — Create / Deploy an App
# =============================================================================

def create_app(
    project_id: str,
    app_name: str,
    image: str,
    port: int = 8080,
    min_instances: int = 0,
    max_instances: int = 10,
    cpu: str = "0.25",
    memory: str = "0.5G",
    env_vars: list = None,
) -> dict:
    """
    Deploy a new application to IBM Cloud Code Engine.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        A unique name for the new application (lowercase, letters/numbers/hyphens).
    image : str
        The container image to deploy.
        Examples:
          - "icr.io/my-namespace/my-app:latest"  (IBM Container Registry)
          - "docker.io/library/nginx:latest"       (Docker Hub)
    port : int
        The port your container listens on. Default: 8080.
    min_instances : int
        Minimum running instances. Use 0 to scale to zero (saves cost). Default: 0.
    max_instances : int
        Maximum instances when traffic is high. Default: 10.
    cpu : str
        CPU allocation (e.g. "0.25", "0.5", "1", "2"). Default: "0.25".
    memory : str
        Memory allocation (e.g. "0.5G", "1G", "2G", "4G"). Default: "0.5G".
    env_vars : list of dict, optional
        Environment variables. Format: [{"name": "MY_VAR", "value": "hello"}]

    Returns
    -------
    dict
        The created app details including its public URL.
    """
    if not project_id or not app_name or not image:
        return {"error": "project_id, app_name, and image are all required."}

    payload = {
        "name": app_name,
        "image_reference": image,
        "image_port": port,
        "scale_min_instances": min_instances,
        "scale_max_instances": max_instances,
        "scale_cpu_limit": cpu,
        "scale_memory_limit": memory,
    }

    if env_vars:
        payload["run_env_variables"] = env_vars

    url = f"{CE_API_BASE}/projects/{project_id}/apps"
    response = requests.post(url, headers=auth_headers(), json=payload, timeout=60)

    if response.status_code in (200, 201):
        app = response.json()
        return {
            "success": True,
            "message": f"App '{app_name}' is being deployed.",
            "name": app.get("name"),
            "status": app.get("status"),
            "url": app.get("endpoint"),
            "note": "It may take 1-2 minutes to become fully ready.",
        }

    return {"error": f"Failed to create app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 5 — Delete an App
# =============================================================================

def delete_app(project_id: str, app_name: str) -> dict:
    """
    Delete a Code Engine application.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application to delete.

    Returns
    -------
    dict
        Confirmation of deletion.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}

    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.delete(url, headers=auth_headers(), timeout=30)

    if response.status_code == 202:
        return {"success": True, "message": f"App '{app_name}' is being deleted."}
    if response.status_code == 404:
        return {"error": f"App '{app_name}' not found."}

    return {"error": f"Failed to delete app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 6 — List Jobs
# =============================================================================

def list_jobs(project_id: str) -> dict:
    """
    List all batch jobs defined in a Code Engine project.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.

    Returns
    -------
    dict
        List of job definitions (not job runs — those are separate executions).
    """
    if not project_id:
        return {"error": "project_id is required."}

    url = f"{CE_API_BASE}/projects/{project_id}/jobs"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code != 200:
        return {"error": f"Failed to list jobs: {response.status_code} — {response.text}"}

    data = response.json()
    jobs = [
        {
            "name": j.get("name"),
            "image": j.get("image_reference"),
            "cpu": j.get("scale_cpu_limit"),
            "memory": j.get("scale_memory_limit"),
            "created_at": j.get("created_at"),
        }
        for j in data.get("jobs", [])
    ]

    return {"jobs": jobs, "count": len(jobs)}


# =============================================================================
# TOOL 7 — Create a Job Run (trigger a batch job)
# =============================================================================

def create_job_run(project_id: str, job_name: str, array_indices: str = "0") -> dict:
    """
    Trigger a run of a Code Engine batch job.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    job_name : str
        The name of the job definition to run.
    array_indices : str
        Which job array indices to run. "0" runs one instance.
        Use "0-4" to run instances 0,1,2,3,4 in parallel.
        Default: "0"

    Returns
    -------
    dict
        The job run ID and initial status. Use get_job_run_status() to poll.
    """
    if not project_id or not job_name:
        return {"error": "project_id and job_name are required."}

    payload = {
        "job_name": job_name,
        "scale_array_spec": array_indices,
    }

    url = f"{CE_API_BASE}/projects/{project_id}/job_runs"
    response = requests.post(url, headers=auth_headers(), json=payload, timeout=30)

    if response.status_code in (200, 201):
        run = response.json()
        return {
            "success": True,
            "job_run_name": run.get("name"),
            "status": run.get("status"),
            "message": f"Job '{job_name}' has been triggered. Use get_job_run_status() to check progress.",
        }

    return {"error": f"Failed to create job run: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 8 — Get Job Run Status
# =============================================================================

def get_job_run_status(project_id: str, job_run_name: str) -> dict:
    """
    Check the status of a Code Engine job run.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    job_run_name : str
        The name of the job run (returned by create_job_run()).

    Returns
    -------
    dict
        Status details including succeeded/failed/pending instance counts.
    """
    if not project_id or not job_run_name:
        return {"error": "project_id and job_run_name are required."}

    url = f"{CE_API_BASE}/projects/{project_id}/job_runs/{job_run_name}"
    response = requests.get(url, headers=auth_headers(), timeout=30)

    if response.status_code == 404:
        return {"error": f"Job run '{job_run_name}' not found."}
    if response.status_code != 200:
        return {"error": f"Failed to get job run: {response.status_code} — {response.text}"}

    run = response.json()
    status = run.get("status_details", {})

    return {
        "job_run_name": run.get("name"),
        "job_name": run.get("job_name"),
        "status": run.get("status"),
        "instances": {
            "succeeded": status.get("succeeded", 0),
            "failed": status.get("failed", 0),
            "pending": status.get("pending", 0),
            "running": status.get("running", 0),
        },
        "started_at": run.get("status_details", {}).get("start_time"),
        "completed_at": run.get("status_details", {}).get("completion_time"),
    }


# =============================================================================
# ADK Tool Registration — maps tool names to functions
# =============================================================================

CODE_ENGINE_TOOLS = [
    {
        "name": "list_code_engine_projects",
        "description": "List all IBM Cloud Code Engine projects in the account.",
        "function": list_code_engine_projects,
        "parameters": {},
    },
    {
        "name": "list_code_engine_apps",
        "description": "List all applications in a Code Engine project.",
        "function": list_code_engine_apps,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
        },
    },
    {
        "name": "get_app_details",
        "description": "Get detailed info about a Code Engine application.",
        "function": get_app_details,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "create_app",
        "description": "Deploy a new containerized application to Code Engine.",
        "function": create_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "Name for the new app."},
            "image": {"type": "string", "description": "Container image (e.g. icr.io/ns/app:latest)."},
            "port": {"type": "integer", "description": "Port the container listens on. Default 8080."},
            "min_instances": {"type": "integer", "description": "Min running instances. Default 0."},
            "max_instances": {"type": "integer", "description": "Max instances. Default 10."},
            "cpu": {"type": "string", "description": "CPU limit (e.g. '0.25'). Default '0.25'."},
            "memory": {"type": "string", "description": "Memory limit (e.g. '0.5G'). Default '0.5G'."},
        },
    },
    {
        "name": "delete_app",
        "description": "Delete a Code Engine application.",
        "function": delete_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The app to delete."},
        },
    },
    {
        "name": "list_jobs",
        "description": "List all batch jobs defined in a Code Engine project.",
        "function": list_jobs,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
        },
    },
    {
        "name": "create_job_run",
        "description": "Trigger a Code Engine batch job run.",
        "function": create_job_run,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "job_name": {"type": "string", "description": "Job definition to run."},
            "array_indices": {"type": "string", "description": "Indices to run. Default '0'."},
        },
    },
    {
        "name": "get_job_run_status",
        "description": "Check the status of a Code Engine job run.",
        "function": get_job_run_status,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "job_run_name": {"type": "string", "description": "Job run name from create_job_run()."},
        },
    },
]


# =============================================================================
# Quick test — run this file directly to verify Code Engine connection
# =============================================================================
if __name__ == "__main__":
    print("Testing Code Engine Tools...")
    result = list_code_engine_projects()
    print(json.dumps(result, indent=2))
