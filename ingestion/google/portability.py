"""Google Data Portability API client — shared by Maps + YouTube ingest.

Per-tick flow inside a Dagster asset:
  1. archives.initiate(resource_list, time_range) → archive job ID
  2. poll archiveJobs.getPortabilityArchiveState until status COMPLETE
  3. GET each signed URL → unpack the zip archive (same layout as Takeout)
  4. parse the JSON files and INSERT into bronze.<source>_*

This module handles steps 1-3; per-source `parser.py` modules handle step 4.

Notes:
  - The DP REST API surface is at
    https://dataportability.googleapis.com/v1/. We call it with raw
    googleapiclient.discovery.build via the discovery doc.
  - Archive completion can take minutes (incremental) to hours (initial 1y
    backfill) — callers should set a generous timeout.
  - Signed URLs in the response are S3-style and expire ~1 hour after issue.
"""

from __future__ import annotations

import io
import logging
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials


log = logging.getLogger(__name__)

BASE_URL = "https://dataportability.googleapis.com/v1"
DEFAULT_POLL_INTERVAL_S = 15


@dataclass
class ArchiveJob:
    job_id: str
    state: str
    signed_urls: list[str]


class DataPortabilityClient:
    """Thin wrapper around the Data Portability REST API."""

    def __init__(self, creds: Credentials):
        self._session = AuthorizedSession(creds)

    def initiate_archive(
        self,
        resources: list[str],
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        body: dict[str, Any] = {"resources": resources}
        if start_time and end_time:
            body["startTime"] = start_time.astimezone(timezone.utc).isoformat()
            body["endTime"] = end_time.astimezone(timezone.utc).isoformat()
        resp = self._session.post(f"{BASE_URL}/portabilityArchive:initiate", json=body, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"initiate failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        # Response shape: {"archiveJobId": "..."}
        job_id = data.get("archiveJobId") or data.get("name", "").split("/")[-1]
        if not job_id:
            raise RuntimeError(f"initiate response missing archiveJobId: {data}")
        log.info("Initiated archive job %s for %d resources", job_id, len(resources))
        return job_id

    def get_state(self, job_id: str) -> ArchiveJob:
        resp = self._session.get(
            f"{BASE_URL}/archiveJobs/{job_id}/portabilityArchiveState",
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"getState failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        return ArchiveJob(
            job_id=job_id,
            state=data.get("state", "STATE_UNSPECIFIED"),
            signed_urls=list(data.get("urls") or []),
        )

    def wait_for_archive(self, job_id: str, *, timeout_s: int = 3600) -> ArchiveJob:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            job = self.get_state(job_id)
            log.info("Archive %s state=%s", job_id, job.state)
            if job.state == "COMPLETE":
                return job
            if job.state in {"FAILED", "EXPIRED", "CANCELLED"}:
                raise RuntimeError(f"archive {job_id} ended in state {job.state}")
            time.sleep(DEFAULT_POLL_INTERVAL_S)
        raise TimeoutError(f"archive {job_id} did not complete within {timeout_s}s")

    def download_archive(self, job: ArchiveJob, dest_dir: Path) -> Path:
        """Download every signed URL into dest_dir, unzipping zip payloads."""

        dest_dir.mkdir(parents=True, exist_ok=True)
        for idx, url in enumerate(job.signed_urls):
            resp = requests.get(url, timeout=300, stream=True)
            if not resp.ok:
                raise RuntimeError(f"download {idx} failed ({resp.status_code}): {resp.text[:200]}")
            buf = io.BytesIO(resp.content)
            if zipfile.is_zipfile(buf):
                buf.seek(0)
                with zipfile.ZipFile(buf) as zf:
                    zf.extractall(dest_dir)
                log.info("Unzipped archive part %d into %s", idx, dest_dir)
            else:
                # Some endpoints return a plain JSON/NDJSON file directly.
                fname = dest_dir / f"part_{idx}.bin"
                fname.write_bytes(buf.getvalue())
                log.info("Saved archive part %d → %s", idx, fname)
        return dest_dir


def walk_files(root: Path, *suffixes: str) -> Iterable[Path]:
    """Yield every file under root matching one of the suffixes."""
    for path in root.rglob("*"):
        if path.is_file() and (not suffixes or path.suffix.lower() in suffixes):
            yield path
