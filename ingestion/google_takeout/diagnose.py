#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot Google Data Portability API 403 errors.
"""

import os
import sys
import pickle
import requests
from google.oauth2.credentials import Credentials

# Paths
TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'tokens', '.google_portability_token.pickle')
API_URL = "https://dataportability.googleapis.com/v1/portabilityArchive:initiate"

print("=" * 70)
print("Google Data Portability API Diagnostic Tool")
print("=" * 70)
print()

# 1. Check if token file exists
print(f"1. Checking token file: {TOKEN_PATH}")
if not os.path.exists(TOKEN_PATH):
    print("   ❌ Token file not found!")
    sys.exit(1)
print("   ✓ Token file exists")
print()

# 2. Load and inspect token
print("2. Loading token...")
try:
    with open(TOKEN_PATH, 'rb') as f:
        creds = pickle.load(f)
    print(f"   ✓ Token loaded successfully")
    print(f"   Token valid: {creds.valid}")
    print(f"   Token expired: {creds.expired}")
    print(f"   Has refresh token: {creds.refresh_token is not None}")
    print(f"   Scopes: {creds.scopes}")
    print()
except Exception as e:
    print(f"   ❌ Failed to load token: {e}")
    sys.exit(1)

# 3. Check scopes
print("3. Verifying scopes...")
required_scopes = [
    'https://www.googleapis.com/auth/dataportability.myactivity.maps',
    'https://www.googleapis.com/auth/dataportability.myactivity.youtube'
]
for scope in required_scopes:
    if scope in creds.scopes:
        print(f"   ✓ {scope}")
    else:
        print(f"   ❌ Missing: {scope}")
print()

# 4. Test API call
print("4. Making test API call to Data Portability API...")
headers = {
    'Authorization': f'Bearer {creds.token}',
    'Content-Type': 'application/json'
}
payload = {
    "resources": ["myactivity.maps"]
}

try:
    response = requests.post(API_URL, headers=headers, json=payload)
    print(f"   Status Code: {response.status_code}")
    print(f"   Response Headers: {dict(response.headers)}")
    print()

    if response.status_code == 403:
        print("   ❌ 403 Forbidden Error Details:")
        print(f"   Response body: {response.text}")
        print()
        print("   Common causes:")
        print("   - Data Portability API not enabled in Google Cloud Console")
        print("   - OAuth consent screen not configured properly")
        print("   - App is in 'Testing' mode and your account isn't a test user")
        print("   - API access not yet approved by Google")
        print()
        print("   Steps to fix:")
        print("   1. Go to: https://console.cloud.google.com/apis/library/dataportability.googleapis.com")
        print("   2. Enable the 'Google Data Portability API'")
        print("   3. Check OAuth consent screen configuration")
        print("   4. If in Testing mode, add your email as a test user")
    elif response.status_code == 200:
        print("   ✓ API call successful!")
        print(f"   Response: {response.json()}")
    else:
        print(f"   ⚠ Unexpected status code: {response.status_code}")
        print(f"   Response: {response.text}")

except Exception as e:
    print(f"   ❌ API call failed: {e}")
    sys.exit(1)

print()
print("=" * 70)
