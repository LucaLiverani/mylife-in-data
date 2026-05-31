"""Resolve an importer's input arg to a local directory the parsers can walk.

Accepts either:
  - a local path: a `.zip`, or an already-extracted directory; or
  - an R2 location `r2://<key-or-prefix>` — a single object key, or a prefix
    matching several objects (e.g. a multi-part Takeout `r2://google-takeout/`).

R2 objects are streamed to a temp dir (never held in memory), any `.zip` found
is extracted, and every temp dir is removed on context exit. Yields the root
directory to hand to the parsers.

    from ingestion._shared.import_source import open_archive_root
    with open_archive_root(arg) as root:
        rows = parse_something(root)   # do all reads before the block exits
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

R2_SCHEME = "r2://"


def is_r2_uri(arg: str) -> bool:
    return arg.startswith(R2_SCHEME)


def _gather_from_r2(arg: str, into: Path) -> Path:
    """Download every object matching the r2://<key-or-prefix> into `into`."""
    from . import r2

    key = arg[len(R2_SCHEME):]
    if not key:
        raise ValueError(f"Empty R2 key in {arg!r}")
    keys = r2.list_keys(key)
    if not keys:
        raise FileNotFoundError(
            f"No R2 objects match {arg!r} (bucket {os.environ.get('R2_BUCKET')!r})"
        )
    for k in keys:
        dest = into / Path(k).name
        r2.download_file(k, dest)
        log.info("Downloaded r2://%s -> %s (%d bytes)", k, dest.name, dest.stat().st_size)
    return into


@contextlib.contextmanager
def open_archive_root(arg: str) -> Iterator[Path]:
    """Yield a local directory ready for parsers to rglob. See module docstring."""
    tmpdirs: list[Path] = []
    try:
        if is_r2_uri(arg):
            dl = Path(tempfile.mkdtemp(prefix="r2-dl-"))
            tmpdirs.append(dl)
            src = _gather_from_r2(arg, dl)
        else:
            src = Path(arg)
            if not src.exists():
                raise FileNotFoundError(f"Path not found: {src}")

        # Extract any zips (a single zip, or several from a multi-part export).
        if src.is_file() and zipfile.is_zipfile(src):
            zips = [src]
        elif src.is_dir():
            zips = sorted(p for p in src.glob("*.zip") if zipfile.is_zipfile(p))
        else:
            zips = []

        if zips:
            extracted = Path(tempfile.mkdtemp(prefix="archive-"))
            tmpdirs.append(extracted)
            for z in zips:
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(extracted)
                log.info("Extracted %s", z.name)
            yield extracted
        elif src.is_dir():
            yield src  # already-extracted tree
        else:
            yield src.parent  # a single non-zip file (e.g. one MyActivity.json)
    finally:
        for d in tmpdirs:
            shutil.rmtree(d, ignore_errors=True)
