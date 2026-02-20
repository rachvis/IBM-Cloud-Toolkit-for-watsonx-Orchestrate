# IBM Cloud Toolkit for watsonx Orchestrate on IBM Cloud
## Complete Setup & Usage Guide

---

## 🗺️ Table of Contents

1. [What is This?](#what-is-this)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Verifying Your Setup](#verifying-your-setup)
6. [Available Tools Reference](#available-tools-reference)
7. [Importing into watsonx Orchestrate on IBM Cloud](#importing-into-watsonx-orchestrate-on-ibm-cloud)
8. [Creating Your First Agent](#creating-your-first-agent)
9. [Example Agent Conversations](#example-agent-conversations)
10. [Troubleshooting](#troubleshooting)
11. [Adding Custom Tools](#adding-custom-tools)

---

## What is This?

The **IBM Cloud Toolkit for watsonx Orchestrate on IBM Cloud** is a collection of tools that let an AI agent in **watsonx Orchestrate** (deployed on IBM Cloud) talk directly to your IBM Cloud account.

```
You (plain English)
    ↕
watsonx Orchestrate Agent (on IBM Cloud)
    ↕
IBM Cloud Toolkit (this toolkit — loaded as skills)
    ↕
IBM Cloud APIs (Code Engine, Logs, Monitoring, Databases)
    ↕
Your IBM Cloud Infrastructure
```

Instead of clicking around the IBM Cloud Console, you can say:

> *"What Code Engine apps are running right now?"*

> *"Show me all error logs from the past 2 hours"*

> *"Scale my PostgreSQL database to 8 GB memory"*

---

## Architecture Overview

```
ibm-cloud-toolkit/
│
├── install.sh                    ← Run once to configure everything
├── .env                          ← Your IBM Cloud + Orchestrate credentials
├── requirements.txt              ← Python dependencies
│
├── tools/
│   ├── ibm_auth.py               ← IAM token management (shared)
│   ├── code_engine_tools.py      ← 8 tools for Code Engine
│   ├── cloud_logs_tools.py       ← 6 tools for Cloud Logs
│   ├── cloud_monitoring_tools.py ← 6 tools for Cloud Monitoring
│   ├── databases_tools.py        ← 8 tools for IBM Cloud Databases
│   ├── register_tools.py         ← Generates OpenAPI spec
│   ├── export_to_orchestrate.py  ← Import guide & API helper
│   └── test_connection.py        ← Verifies IBM Cloud connection
│
├── config/                       ← Auto-generated after install
│   ├── ibm_cloud_toolkit_openapi.json  ← Upload to watsonx Orchestrate
│   ├── tool_manifest.json
│   └── tools_summary.txt
│
└── docs/
    └── GUIDE.md                  ← This file
```

---

## Prerequisites

| Requirement | How to Get It |
|-------------|---------------|
| IBM Cloud Account | [cloud.ibm.com/registration](https://cloud.ibm.com/registration) |
| IBM Cloud API Key | IBM Cloud Console → Manage → Access (IAM) → API Keys → Create |
| watsonx Orchestrate on IBM Cloud | IBM Cloud Catalog → AI / Machine Learning → watsonx Orchestrate |
| Orchestrate Instance URL | IBM Cloud Console → Resource list → your Orchestrate instance → Manage → Credentials |
| Python 3.9+ | [python.org](https://python.org) or `brew install python3` |
| Git | [git-scm.com](https://git-scm.com) or `brew install git` |

> **Finding your watsonx Orchestrate Instance URL:**
> IBM Cloud Console → ☰ Menu → Resource list → AI / Machine Learning →
> click your **watsonx Orchestrate** instance → **Manage** tab → copy the **URL** from Credentials.
> It looks like: `https://cpd-<namespace>.<cluster>.us-south.containers.appdomain.cloud`

---

## Installation

### Step 1 — Clone the toolkit

```bash
git clone https://github.com/your-org/ibm-cloud-toolkit.git
cd ibm-cloud-toolkit
```

### Step 2 — Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer will prompt you for:
- Your **IBM Cloud API Key**
- Your **IBM Cloud Region** (e.g. `us-south`, `eu-de`, `jp-tok`)
- Your **Resource Group** (usually `Default`)
- Your **watsonx Orchestrate Instance URL**

It then automatically:
- Creates a `.env` file with all credentials
- Sets up a Python virtual environment
- Installs all dependencies
- Tests your IBM Cloud connection
- Generates the OpenAPI spec at `config/ibm_cloud_toolkit_openapi.json`

**Takes about 2–3 minutes.**

### Step 3 — Done 🎉

Your OpenAPI spec is ready to import into watsonx Orchestrate on IBM Cloud.

---

## Verifying Your Setup

```bash
source venv/bin/activate
python3 tools/test_connection.py
```

Expected output:
```
Testing IBM Cloud connection...
  Region: us-south
  ✅ Authentication successful! (token length: 1234 chars)
```

Test individual service tools:
```bash
python3 tools/code_engine_tools.py       # Lists Code Engine projects
python3 tools/cloud_logs_tools.py        # Lists Cloud Logs instances
python3 tools/cloud_monitoring_tools.py  # Lists monitoring instances
python3 tools/databases_tools.py         # Lists database instances
```

---

## Available Tools Reference

### 📦 IBM Cloud Code Engine (8 tools)

| Tool | What it Does |
|------|-------------|
| `list_code_engine_projects` | List all Code Engine projects |
| `list_code_engine_apps` | List apps in a project |
| `get_app_details` | Detailed app info (URL, instances, config) |
| `create_app` | Deploy a new containerized app |
| `delete_app` | Remove an app |
| `list_jobs` | List batch job definitions |
| `create_job_run` | Trigger a batch job run |
| `get_job_run_status` | Check if a job run completed |

### 📋 IBM Cloud Logs (6 tools)

| Tool | What it Does |
|------|-------------|
| `list_log_instances` | List Cloud Logs instances |
| `search_logs` | Search logs by text query |
| `get_recent_logs` | Get the most recent log lines |
| `get_logs_by_severity` | Filter by ERROR, CRITICAL, WARNING, etc. |
| `count_errors` | Count issues and get a health summary |
| `get_log_alerts` | List configured alert rules |

### 📊 IBM Cloud Monitoring (6 tools)

| Tool | What it Does |
|------|-------------|
| `list_monitoring_instances` | List monitoring instances |
| `query_metric` | Query CPU, memory, network, custom metrics |
| `get_platform_metrics` | Query metrics from IBM platform services |
| `list_alerts` | List monitoring alert rules |
| `get_alert_events` | Get recent alert firings |
| `get_team_dashboards` | List available dashboards |

### 🗄️ IBM Cloud Databases (8 tools)

| Tool | What it Does |
|------|-------------|
| `list_database_instances` | List all database instances (filter by type) |
| `get_database_details` | Detailed instance info |
| `list_database_backups` | List available backups |
| `create_manual_backup` | Trigger an immediate backup |
| `get_connection_strings` | Get hostname, port, TLS info (no passwords) |
| `scale_database` | Increase/decrease memory, disk, CPU |
| `list_database_tasks` | Monitor ongoing operations |
| `get_database_whitelist` | View IP allowlist rules |

**Total: 28 tools across 4 IBM Cloud services**

---

## Importing into watsonx Orchestrate on IBM Cloud

### Prerequisites

- watsonx Orchestrate instance provisioned on IBM Cloud
- `config/ibm_cloud_toolkit_openapi.json` generated (run `install.sh` first)

---

### Method 1 — IBM Cloud Console UI (Recommended for first import)

1. Log in to [IBM Cloud Console](https://cloud.ibm.com)

2. From the **☰ Navigation menu**, go to:
   **AI / Machine Learning** → **watsonx Orchestrate**

3. Click your **watsonx Orchestrate instance** to open it.

4. In the left sidebar, click **Skills & Apps**

5. Click **+ Add skills** → **From OpenAPI file**

6. Upload:
   ```
   config/ibm_cloud_toolkit_openapi.json
   ```

7. Review the 28 tools → click **Add**

8. Go to **Agent Builder** → open or create your agent → under **Skills**, add **IBM Cloud Toolkit**

---

### Method 2 — watsonx Orchestrate REST API

Use this for automation or CI/CD pipelines.

**Step 1 — Get an IAM token:**
```bash
curl -X POST "https://iam.cloud.ibm.com/identity/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=$IBM_CLOUD_API_KEY"
```

Save the `access_token` from the response.

**Step 2 — Import the OpenAPI spec:**
```bash
ORCHESTRATE_URL="https://your-instance.orchestrate.cloud.ibm.com"
IAM_TOKEN="Bearer eyJ..."

curl -X POST "$ORCHESTRATE_URL/api/v1/skills/import" \
  -H "Authorization: $IAM_TOKEN" \
  -H "Content-Type: application/json" \
  -d @config/ibm_cloud_toolkit_openapi.json
```

---

### Method 3 — IBM Cloud CLI

**Step 1 — Install the IBM Cloud CLI:**
```bash
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh   # macOS
# or
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh  # Linux
```

**Step 2 — Log in:**
```bash
ibmcloud login --apikey $IBM_CLOUD_API_KEY -r us-south
```

**Step 3 — Target your Orchestrate resource group:**
```bash
ibmcloud target -g Default
ibmcloud resource service-instances --service-name watsonx-orchestrate
```

**Step 4 — Import via the Orchestrate API using the CLI's token:**
```bash
TOKEN=$(ibmcloud iam oauth-tokens --output json | jq -r '.iam_token')
ORCHESTRATE_URL="https://your-instance.orchestrate.cloud.ibm.com"

curl -X POST "$ORCHESTRATE_URL/api/v1/skills/import" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d @config/ibm_cloud_toolkit_openapi.json
```

---

### Regenerate the spec anytime

If you modify or add tools:
```bash
source venv/bin/activate
python3 tools/register_tools.py
# Then re-import config/ibm_cloud_toolkit_openapi.json into Orchestrate
```

---

## Creating Your First Agent

Once skills are imported in watsonx Orchestrate on IBM Cloud:

1. Go to **Agent Builder** in your Orchestrate instance
2. Click **Create Agent** → name it `IBM Cloud Ops Agent`
3. Add this system prompt:

```
You are an IBM Cloud operations assistant with access to tools for
managing IBM Cloud Code Engine, Cloud Logs, Cloud Monitoring,
and IBM Cloud Databases.

- For application or deployment questions → use Code Engine tools
- For log, error, or debugging questions → use Cloud Logs tools
- For metrics or performance questions → use Monitoring tools
- For database questions → use Databases tools

Present information clearly. Flag resource usage over 80% as a warning.
For error counts, label the situation as healthy, degraded, or critical.
```

4. Under **Skills**, add **IBM Cloud Toolkit**
5. Click **Deploy**

---

## Example Agent Conversations

### Health Check
```
User:  Give me a quick health check of my IBM Cloud environment

Agent: Checking Code Engine, Logs, and Monitoring...

       Code Engine: 3 projects, 12 apps running ✅
       Cloud Logs: 45 errors in the last hour ⚠️ (DEGRADED)
       Monitoring: CPU 34% avg, Memory 62% avg ✅

       Recommendation: Review the error logs from the past hour.
```

### Debugging
```
User:  Show me error logs from the last 30 minutes

Agent: Searching Cloud Logs for errors...
       Found 23 events:
       - [10:23] ConnectionTimeoutException in orders-service
       - [10:24] Database connection pool exhausted
       ...
```

### Scaling
```
User:  Scale my PostgreSQL production database to 8GB memory

Agent: Scaling initiated — 4096 MB → 8192 MB
       Task ID: task-abc123
       This will take ~10 minutes. Say "check database tasks" to monitor.
```

### Deployment
```
User:  Deploy backend-api from image icr.io/myns/api:v2.1

Agent: ✅ App deployment initiated!
       Project: production
       URL: https://backend-api.abc123.us-south.codeengine.appdomain.cloud
       Status: deploying (~2 minutes to ready)
```

---

## Troubleshooting

### "IBM_CLOUD_API_KEY not found"
```bash
cat .env | grep IBM_CLOUD_API_KEY   # verify key is present
./install.sh                         # re-run installer if missing
```

### "Authentication failed: 401"
Your API key may be expired. Create a new one:
IBM Cloud Console → Manage → Access (IAM) → API Keys → Create → update `.env`

### "Failed to list: 403 Forbidden"
Your API key doesn't have permission for that service.
IBM Cloud Console → Manage → Access (IAM) → Users → your user → Access policies → Add access

### "Orchestrate import fails"
- Validate the spec: `python3 -c "import json; json.load(open('config/ibm_cloud_toolkit_openapi.json'))"`
- Confirm your Orchestrate instance URL is correct in `.env`
- Check that your IBM Cloud account has the Orchestrate instance in **Active** state

### watsonx Orchestrate instance URL not working
Your instance URL should look like one of these:
- `https://cpd-<namespace>.<cluster>.us-south.containers.appdomain.cloud`
- `https://<instance-id>.orchestrate.cloud.ibm.com`

Find the correct URL in: IBM Cloud Console → Resource list → your Orchestrate instance → **Manage** tab

### Tool returns empty list
This is expected if you haven't created those services yet.
For example, `list_code_engine_projects` returns `{"projects": [], "count": 0}` with no projects.

---

## Adding Custom Tools

### 1. Create a new tools file

```python
# tools/my_service_tools.py

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers
import requests

def my_new_tool(param1: str) -> dict:
    """
    Short description of what this tool does.

    Parameters
    ----------
    param1 : str
        What param1 is.

    Returns
    -------
    dict
        What is returned.
    """
    response = requests.get(
        f"https://api.{os.getenv('IBM_CLOUD_REGION')}.myservice.cloud.ibm.com/v1/resource/{param1}",
        headers=auth_headers()
    )
    return response.json()

MY_SERVICE_TOOLS = [
    {
        "name": "my_new_tool",
        "description": "One-sentence description for the AI agent",
        "function": my_new_tool,
        "parameters": {
            "param1": {"type": "string", "description": "What param1 does"},
        },
    }
]
```

### 2. Register it in `tools/register_tools.py`

```python
from my_service_tools import MY_SERVICE_TOOLS

ALL_TOOLS = (
    CODE_ENGINE_TOOLS
    + CLOUD_LOGS_TOOLS
    + MONITORING_TOOLS
    + DATABASES_TOOLS
    + MY_SERVICE_TOOLS   # ← Add here
)
```

### 3. Regenerate and reimport

```bash
python3 tools/register_tools.py
# Then upload config/ibm_cloud_toolkit_openapi.json to watsonx Orchestrate again
```

---

## Security Notes

- Your API key lives only in the local `.env` file
- `.env` is excluded from git (listed in `.gitignore`)
- IBM Cloud IAM tokens expire after 60 minutes — the toolkit refreshes them automatically
- Database connection strings are returned **without passwords**
- For production deployments, store secrets in **IBM Secrets Manager** instead of `.env`

---

## Useful Links

| Resource | URL |
|----------|-----|
| IBM Cloud Console | https://cloud.ibm.com |
| watsonx Orchestrate docs | https://www.ibm.com/docs/en/watsonx/watson-orchestrate |
| IBM Cloud Code Engine docs | https://cloud.ibm.com/docs/codeengine |
| IBM Cloud Logs docs | https://cloud.ibm.com/docs/cloud-logs |
| IBM Cloud Monitoring docs | https://cloud.ibm.com/docs/monitoring |
| IBM Cloud Databases docs | https://cloud.ibm.com/docs/databases-for-postgresql |
| IBM Cloud CLI | https://cloud.ibm.com/docs/cli |
| IBM IAM API Keys | https://cloud.ibm.com/iam/apikeys |
