"""
ibm_auth.py — Shared IBM Cloud Authentication Helper
=====================================================
All tools in this toolkit use this module to get a valid
IBM Cloud IAM access token before making API calls.
"""

import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------- Token cache (avoids fetching a new token every single call) ----------
_token_cache = {
    "access_token": None,
    "expires_at": 0,
}


def get_iam_token() -> str:
    """
    Returns a valid IBM Cloud IAM Bearer token.

    Tokens are cached for 50 minutes (they expire after 60).
    On the first call (or after expiry) a fresh token is fetched
    from IBM's IAM endpoint using your API key.

    Returns
    -------
    str
        A Bearer token string ready to use in Authorization headers.

    Raises
    ------
    EnvironmentError
        If IBM_CLOUD_API_KEY is not set in the environment / .env file.
    RuntimeError
        If the IAM token request fails.
    """
    api_key = os.getenv("IBM_CLOUD_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "IBM_CLOUD_API_KEY not found. "
            "Please set it in your .env file and run install.sh."
        )

    # Return cached token if still valid
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    iam_url = os.getenv(
        "IBM_IAM_TOKEN_URL", "https://iam.cloud.ibm.com/identity/token"
    )

    response = requests.post(
        iam_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to get IAM token: {response.status_code} — {response.text}"
        )

    token_data = response.json()
    _token_cache["access_token"] = token_data["access_token"]
    _token_cache["expires_at"] = time.time() + 3000  # ~50 minutes

    return _token_cache["access_token"]


def auth_headers() -> dict:
    """
    Returns a dict with Authorization + Content-Type headers.
    Ready to pass directly into requests calls.
    """
    return {
        "Authorization": f"Bearer {get_iam_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_region() -> str:
    return os.getenv("IBM_CLOUD_REGION", "us-south")


def get_resource_group() -> str:
    return os.getenv("IBM_CLOUD_RESOURCE_GROUP", "Default")
