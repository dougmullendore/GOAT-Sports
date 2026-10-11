"""Downloading, with retries."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config


class FetchError(RuntimeError):
    pass


def _saved(url: str) -> bytes | None:
    """For the tests and for working on the site away from the internet: with
    FETCH_CACHE set to a folder, a file saved there under the address's name is
    used instead of downloading (see tests/fixtures)."""
    folder = os.environ.get("FETCH_CACHE")
    if not folder:
        return None
    path = Path(folder) / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".gz")
    if path.exists():
        return gzip.decompress(path.read_bytes())
    raise FetchError(f"not among the saved files: {url[:100]}")


def get_bytes(url: str, timeout: int = 60, tries: int | None = None) -> bytes:
    saved = _saved(url)
    if saved is not None:
        return saved
    last = None
    for attempt in range(tries or config.FETCH_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return raw
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 403, 404):
                break
        except Exception as e:  # network errors, timeouts
            last = e
        time.sleep(min(30, 1.5 * 2 ** attempt) + random.random())
    raise FetchError(f"could not download {url[:100]}: {last!r}")


def get_json(url: str, tries: int | None = None) -> dict:
    return json.loads(get_bytes(url, tries=tries))


def get_many(urls: list[str], tries: int | None = None):
    """Download many addresses at once. Yields (url, document or None, error or None), in order."""
    def one(url):
        try:
            return url, get_json(url, tries), None
        except Exception as e:
            return url, None, e

    with ThreadPoolExecutor(max_workers=config.FETCH_THREADS) as pool:
        yield from pool.map(one, urls)
