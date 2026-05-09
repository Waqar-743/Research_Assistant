"""
Sync GitHub-secret env vars → Render service env vars via Render Management API.

Environment variables expected (all optional — missing ones are skipped):
  RENDER_API_KEY       Render account API key
  SERVICE_ID           Render service ID (e.g. srv-xxxx)
  S_MONGODB_URL        Value for MONGODB_URL on Render
  S_OPENROUTER_API_KEY Value for OPENROUTER_API_KEY on Render
  S_SERPAPI_KEY        Value for SERPAPI_KEY on Render
  S_NEWSAPI_KEY        Value for NEWSAPI_KEY on Render
  S_SENTRY_DSN         Value for SENTRY_DSN on Render
"""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

api_key = os.environ.get("RENDER_API_KEY", "")
svc = os.environ.get("SERVICE_ID", "")

if not api_key or not svc:
    print("RENDER_API_KEY or SERVICE_ID not set — skipping env sync.")
    sys.exit(0)

inject = {
    k: v
    for k, v in {
        "MONGODB_URL": os.environ.get("S_MONGODB_URL", ""),
        "OPENROUTER_API_KEY": os.environ.get("S_OPENROUTER_API_KEY", ""),
        "SERPAPI_KEY": os.environ.get("S_SERPAPI_KEY", ""),
        "NEWSAPI_KEY": os.environ.get("S_NEWSAPI_KEY", ""),
        "SENTRY_DSN": os.environ.get("S_SENTRY_DSN", ""),
    }.items()
    if v
}

if not inject:
    print("No secrets configured in GitHub — skipping env sync.")
    sys.exit(0)

hdrs = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# GET current env vars from Render
try:
    with urlopen(
        Request(f"https://api.render.com/v1/services/{svc}/env-vars", headers=hdrs)
    ) as r:
        current = json.load(r)
except HTTPError as e:
    print(f"GET env vars failed: {e.code} — {e.read().decode()}")
    sys.exit(1)

# Normalize to key→value dict (Render returns cursor-paged or flat lists)
evars = {}
for item in current:
    ev = item.get("envVar", item)
    evars[ev["key"]] = ev.get("value", "")

# Merge secrets in
evars.update(inject)

# PUT merged env vars back
payload = json.dumps(
    {"envVars": [{"key": k, "value": v} for k, v in evars.items()]}
).encode()

try:
    with urlopen(
        Request(
            f"https://api.render.com/v1/services/{svc}/env-vars",
            data=payload,
            headers=hdrs,
            method="PUT",
        )
    ) as r:
        print(f"Synced {len(inject)} secret(s) to Render: {list(inject.keys())}")
except HTTPError as e:
    print(f"PUT env vars failed: {e.code} — {e.read().decode()}")
    sys.exit(1)
