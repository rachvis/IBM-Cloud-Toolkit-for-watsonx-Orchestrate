"""
test_connection.py — Verify IBM Cloud Credentials
===================================================
Run this script to confirm your IBM Cloud API key is valid
and can authenticate successfully.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ibm_auth import get_iam_token, get_region

def test_connection():
    print("Testing IBM Cloud connection...")
    print(f"  Region: {get_region()}")

    try:
        token = get_iam_token()
        if token and len(token) > 50:
            print(f"  ✅ Authentication successful! (token length: {len(token)} chars)")
            return True
        else:
            print("  ❌ Got a token but it looks invalid.")
            return False
    except EnvironmentError as e:
        print(f"  ❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        print("     Check your IBM_CLOUD_API_KEY in the .env file.")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
