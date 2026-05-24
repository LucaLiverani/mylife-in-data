"""Round-trip an R2 connection check.

Verifies the R2 credentials in infrastructure/.env can:
  1. authenticate (ListBuckets)
  2. resolve the configured bucket
  3. PUT a small object
  4. GET the same object back
  5. DELETE it

Each step prints what it did and the likely root cause if it failed.

Usage (from repo root, with .venv active):
    .venv/bin/python scripts/test_r2_connection.py

Or inside the running stack:
    docker exec dagster-webserver python /opt/dagster/repo/scripts/test_r2_connection.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load infrastructure/.env when run on the host. Inside Dagster containers the
# values come from compose env passthrough and python-dotenv just no-ops.
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / "infrastructure" / ".env")
except ImportError:
    pass


REQUIRED_VARS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_ENDPOINT")
TEST_KEY = "_healthcheck/r2-probe.txt"


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str, *, hint: str | None = None) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)
    if hint:
        print(f"    → {hint}", file=sys.stderr)


def check_env() -> bool:
    print("[1/5] env vars")
    missing = [k for k in REQUIRED_VARS if not os.environ.get(k)]
    if missing:
        _fail(
            f"missing in env: {missing}",
            hint="fill them in infrastructure/.env (gitignored) and re-run",
        )
        return False
    endpoint = os.environ["R2_ENDPOINT"]
    bucket = os.environ["R2_BUCKET"]
    # Catch the common "bucket appended to endpoint URL" mistake.
    if endpoint.rstrip("/").endswith(f"/{bucket}"):
        _fail(
            f"R2_ENDPOINT has the bucket name appended: {endpoint}",
            hint=f"strip the trailing /{bucket} — boto3 passes the bucket separately",
        )
        return False
    _ok(f"all 5 vars set; endpoint={endpoint}; bucket={bucket}")
    return True


def check_list_buckets() -> tuple[bool, object | None]:
    """Auth check + ensures the configured bucket is visible to this token."""
    print("[2/5] ListBuckets (auth check)")
    try:
        from ingestion._shared.r2 import get_client
    except ImportError as e:
        _fail(f"can't import boto3 helper: {e}", hint="run `.venv/bin/pip install boto3 python-dotenv`")
        return False, None

    client = get_client()
    try:
        resp = client.list_buckets()
    except Exception as exc:
        msg = str(exc)
        hint = None
        if "InvalidAccessKeyId" in msg:
            hint = "Access Key ID is wrong — confirm it matches the token's `id` field"
        elif "SignatureDoesNotMatch" in msg:
            hint = "Secret Access Key is wrong — roll the token and copy fresh credentials"
        elif "AccessDenied" in msg or "Forbidden" in msg:
            # Bucket-scoped tokens can't ListBuckets — that's expected, not a failure.
            print(f"  ! ListBuckets forbidden (expected for object-scoped tokens); deferring verdict to PUT/GET")
            return True, client
        _fail(f"list_buckets failed: {msg[:200]}", hint=hint)
        return False, None

    names = [b.get("Name") for b in (resp.get("Buckets") or [])]
    bucket = os.environ["R2_BUCKET"]
    if names and bucket not in names:
        # Bucket-scoped tokens list nothing here — only fail if list returned others.
        _fail(
            f"R2_BUCKET={bucket!r} not in account's bucket list {names}",
            hint="check the bucket exists in this Cloudflare account",
        )
        return False, client
    _ok(f"auth ok; account exposes {len(names)} bucket(s)")
    return True, client


def check_bucket_reachable(client) -> bool:
    """HeadBucket — bucket-level op. Tokens scoped to 'Item Read/Write' (object
    permissions only) will return 403 here, which is expected and not fatal —
    the real verdict is the PUT/GET round-trip below."""
    print("[3/5] HeadBucket (optional)")
    bucket = os.environ["R2_BUCKET"]
    try:
        client.head_bucket(Bucket=bucket)
    except Exception as exc:
        msg = str(exc)
        if "NoSuchBucket" in msg or "404" in msg:
            _fail(
                f"bucket {bucket!r} doesn't exist",
                hint="create it in the R2 dashboard",
            )
            return False
        if "AccessDenied" in msg or "Forbidden" in msg or "403" in msg:
            # Object-only tokens can't HeadBucket — that's fine.
            print(f"  ! head_bucket forbidden (expected for object-scoped tokens); deferring verdict to PUT/GET")
            return True
        _fail(f"head_bucket failed: {msg[:200]}")
        return False
    _ok(f"bucket {bucket!r} is reachable")
    return True


def check_put_get_delete(client) -> bool:
    print("[4/5] PutObject + GetObject round-trip")
    bucket = os.environ["R2_BUCKET"]
    timestamp = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    payload = f"r2 probe at {timestamp}".encode("utf-8")

    try:
        client.put_object(Bucket=bucket, Key=TEST_KEY, Body=payload, ContentType="text/plain")
    except Exception as exc:
        msg = str(exc)
        hint = None
        if "SignatureDoesNotMatch" in msg:
            hint = (
                "R2_SECRET_ACCESS_KEY doesn't match the hash R2 has on file. "
                "The secret can't be re-displayed — Roll the token in the R2 dashboard "
                "and copy the fresh 'Secret Access Key' value from the new modal."
            )
        elif "InvalidAccessKeyId" in msg:
            hint = "Access Key ID isn't recognised — confirm it equals the token's `id` field"
        elif "AccessDenied" in msg or "Forbidden" in msg or "403" in msg:
            hint = "token has Read but not Write — change policy to 'Object Read & Write'"
        _fail(f"put_object failed: {msg[:200]}", hint=hint)
        return False
    _ok(f"PUT {TEST_KEY} ({len(payload)} bytes)")

    try:
        resp = client.get_object(Bucket=bucket, Key=TEST_KEY)
        body = resp["Body"].read()
    except Exception as exc:
        _fail(f"get_object failed: {str(exc)[:200]}")
        return False
    if body != payload:
        _fail(f"GET returned different bytes: {body!r} (sent {payload!r})")
        return False
    _ok(f"GET round-trips: {body.decode()!r}")

    print("[5/5] DeleteObject (cleanup)")
    try:
        client.delete_object(Bucket=bucket, Key=TEST_KEY)
    except Exception as exc:
        # Not fatal — the object is small and self-identifying. Just warn.
        print(f"  ! could not delete {TEST_KEY}: {str(exc)[:120]}")
        return True
    _ok(f"DELETE {TEST_KEY}")
    return True


def main() -> int:
    print(f"R2 connection probe @ {datetime.now(tz=timezone.utc).isoformat(timespec='seconds')}")
    if not check_env():
        return 1
    ok, client = check_list_buckets()
    if not ok or client is None:
        return 2
    if not check_bucket_reachable(client):
        return 3
    if not check_put_get_delete(client):
        return 4
    print("\nR2 connection ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
