"""
register_tools.py — Register All IBM Cloud ADK Tools
=====================================================
This script registers all tools with the watsonx ADK framework
and generates the manifest files needed for import into watsonx Orchestrate.

Run this after install.sh, or whenever you add/modify tools.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from code_engine_tools import CODE_ENGINE_TOOLS
from cloud_logs_tools import CLOUD_LOGS_TOOLS
from cloud_monitoring_tools import MONITORING_TOOLS
from databases_tools import DATABASES_TOOLS

ALL_TOOLS = (
    CODE_ENGINE_TOOLS
    + CLOUD_LOGS_TOOLS
    + MONITORING_TOOLS
    + DATABASES_TOOLS
)


def build_openapi_spec(tools: list) -> dict:
    """
    Build an OpenAPI 3.0 specification from the tool registry.
    watsonx Orchestrate can import tools via OpenAPI specs.
    """
    paths = {}

    for tool in tools:
        path = f"/{tool['name']}"
        properties = {}
        required = []

        for param_name, param_info in tool.get("parameters", {}).items():
            properties[param_name] = {
                "type": param_info.get("type", "string"),
                "description": param_info.get("description", ""),
            }
            # Mark string params without "optional" in description as required
            if "optional" not in param_info.get("description", "").lower() and \
               "default" not in param_info.get("description", "").lower():
                required.append(param_name)

        request_body = None
        if properties:
            request_body = {
                "required": bool(required),
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": properties,
                            "required": required if required else [],
                        }
                    }
                },
            }

        paths[path] = {
            "post": {
                "operationId": tool["name"],
                "summary": tool["description"],
                "description": tool.get("function", lambda: None).__doc__ or tool["description"],
                "requestBody": request_body,
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    },
                    "400": {"description": "Bad request — check parameters"},
                    "401": {"description": "Authentication failed — check IBM Cloud API key"},
                    "500": {"description": "Internal error"},
                },
            }
        }

    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "IBM Cloud Toolkit for watsonx Orchestrate",
            "version": "1.0.0",
            "description": (
                "ADK tools for managing IBM Cloud services including "
                "Code Engine, Cloud Logs, Cloud Monitoring, and IBM Cloud Databases. "
                "Import this spec into watsonx Orchestrate to create AI agents "
                "that can operate IBM Cloud infrastructure."
            ),
            "contact": {
                "name": "IBM Cloud Toolkit",
                "url": "https://cloud.ibm.com",
            },
        },
        "servers": [
            {
                "url": os.getenv(
                    "WATSONX_ORCHESTRATE_INSTANCE_URL",
                    "https://your-instance.orchestrate.cloud.ibm.com"
                ),
                "description": "watsonx Orchestrate on IBM Cloud"
            }
        ],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "IBMCloudApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "IBM Cloud IAM Bearer token. Set IBM_CLOUD_API_KEY in .env",
                }
            }
        },
        "security": [{"IBMCloudApiKey": []}],
    }

    return spec


def build_tool_manifest(tools: list) -> dict:
    """Build a watsonx Orchestrate compatible tool manifest."""
    tool_entries = []
    for tool in tools:
        tool_entries.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": {
                    k: {"type": v.get("type", "string"), "description": v.get("description", "")}
                    for k, v in tool.get("parameters", {}).items()
                },
            },
            "category": _get_category(tool["name"]),
        })

    return {
        "toolkit_name": "ibm-cloud-toolkit",
        "toolkit_version": "1.0.0",
        "toolkit_description": "IBM Cloud management tools for watsonx Orchestrate",
        "tools": tool_entries,
        "tool_count": len(tool_entries),
    }


def _get_category(tool_name: str) -> str:
    if "code_engine" in tool_name or "app" in tool_name or "job" in tool_name:
        return "Code Engine"
    if "log" in tool_name:
        return "Cloud Logs"
    if "monitor" in tool_name or "metric" in tool_name or "alert" in tool_name or "dashboard" in tool_name:
        return "Cloud Monitoring"
    if "database" in tool_name or "backup" in tool_name or "connection" in tool_name or "whitelist" in tool_name or "scale" in tool_name:
        return "IBM Cloud Databases"
    return "General"


def main():
    output_dir = Path(__file__).parent.parent / "config"
    output_dir.mkdir(exist_ok=True)

    # Write OpenAPI spec
    spec = build_openapi_spec(ALL_TOOLS)
    spec_path = output_dir / "ibm_cloud_toolkit_openapi.json"
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"✅  OpenAPI spec written → {spec_path}")

    # Write tool manifest
    manifest = build_tool_manifest(ALL_TOOLS)
    manifest_path = output_dir / "tool_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"✅  Tool manifest written → {manifest_path}")

    # Write human-readable tool list
    summary_lines = [
        "IBM Cloud Toolkit — Available Tools",
        "=" * 50,
        "",
    ]
    categories = {}
    for tool in ALL_TOOLS:
        cat = _get_category(tool["name"])
        categories.setdefault(cat, []).append(tool)

    for cat, cat_tools in categories.items():
        summary_lines.append(f"\n📦 {cat} ({len(cat_tools)} tools)")
        summary_lines.append("-" * 40)
        for t in cat_tools:
            summary_lines.append(f"  • {t['name']}")
            summary_lines.append(f"    {t['description']}")
        summary_lines.append("")

    summary_path = output_dir / "tools_summary.txt"
    with open(summary_path, "w") as f:
        f.write("\n".join(summary_lines))
    print(f"✅  Tool summary written → {summary_path}")

    print(f"\n🎉 Registered {len(ALL_TOOLS)} tools across 4 IBM Cloud services!")
    print(f"\nCategories:")
    for cat, tools in categories.items():
        print(f"   {cat}: {len(tools)} tools")


if __name__ == "__main__":
    main()
