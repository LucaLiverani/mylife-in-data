"""Cloudflare R2 (S3-compatible) helpers — used for replay staging."""

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
