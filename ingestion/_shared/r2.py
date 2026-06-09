"""Cloudflare R2 (S3-compatible) helpers: raw provider exports + the nightly warehouse Parquet archive."""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.client import Config


def get_client() -> Any:
    """boto3 S3 client configured for Cloudflare R2."""

    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    endpoint = os.environ.get(
        "R2_ENDPOINT",
        f"https://{account_id}.r2.cloudflarestorage.com" if account_id else "",
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_bytes(key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET not set")
    get_client().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def download_bytes(key: str) -> bytes:
    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET not set")
    resp = get_client().get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def download_file(key: str, dest: Any) -> None:
    """Stream an object straight to a local file (boto3 managed multipart).

    Use this instead of download_bytes for large blobs (e.g. multi-GB Takeout
    zips) — it never holds the whole object in memory."""
    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET not set")
    get_client().download_file(bucket, key, os.fspath(dest))


def delete_keys(keys: list[str]) -> int:
    """Delete objects in batches of 1000 (the S3 DeleteObjects cap).

    DeleteObjects reports per-key failures inside a 200 response, so check
    the Errors list instead of trusting the status code.
    """
    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET not set")
    client = get_client()
    errors: list[str] = []
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        resp = client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )
        errors.extend(f"{e.get('Key')}: {e.get('Code')}" for e in (resp.get("Errors") or []))
    if errors:
        raise RuntimeError(f"failed to delete {len(errors)} of {len(keys)} object(s): {errors[:5]}")
    return len(keys)


def list_keys(prefix: str) -> list[str]:
    """List object keys under a prefix (paginated). Skips directory markers."""
    bucket = os.environ.get("R2_BUCKET")
    if not bucket:
        raise RuntimeError("R2_BUCKET not set")
    client = get_client()
    keys: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        keys.extend(obj["Key"] for obj in (resp.get("Contents") or []) if not obj["Key"].endswith("/"))
        if not resp.get("IsTruncated"):
            return keys
        token = resp.get("NextContinuationToken")
