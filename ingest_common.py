"""Shared logic of the ingest stage.

This module is never called directly. It encapsulates robust data
acquisition (retry with backoff, hard timeouts, incremental cache, resume
via existence check) and provides it to the lean fetcher scripts.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

import config


def ensure_data_dirs() -> None:
    """Creates the data directories if they are missing."""
    for directory in (config.RAW_DIR, config.INTERIM_DIR, config.CACHE_DIR, config.ARTIFACTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def already_fetched(target_path: Path) -> bool:
    """Resume via existence check: does the target already exist and is it non-empty?"""
    return target_path.exists() and target_path.stat().st_size > 0


def get_with_retry(
    url: str,
    *,
    params: dict[str, str] | None = None,
    timeout: float = config.HTTP_TIMEOUT_SECONDS,
    max_retries: int = config.HTTP_MAX_RETRIES,
) -> requests.Response:
    """GET with exponential backoff on transient server errors.

    Transient errors (429, 500, 502, 503, 504) are retried repeatedly with a
    growing wait time. Permanent errors (e.g. 404) abort immediately.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=config.HTTP_HEADERS, timeout=timeout)
        except requests.RequestException as error:
            last_error = error
        else:
            if response.status_code not in config.HTTP_RETRY_STATUS:
                response.raise_for_status()
                return response
            last_error = requests.HTTPError(f"transient status {response.status_code} for {url}")

        wait_seconds = config.HTTP_BACKOFF_FACTOR ** attempt
        time.sleep(wait_seconds)

    raise RuntimeError(f"fetch failed after {max_retries} attempts: {url}") from last_error


def download_to(url: str, target_path: Path, *, refresh: bool = False) -> Path:
    """Downloads a small file completely to target_path (in memory)."""
    if already_fetched(target_path) and not refresh:
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    response = get_with_retry(url)
    target_path.write_bytes(response.content)
    return target_path


def download_file(
    url: str,
    target_path: Path,
    *,
    refresh: bool = False,
    timeout: float = config.HTTP_TIMEOUT_SECONDS,
    max_retries: int = config.HTTP_MAX_RETRIES,
) -> Path:
    """Downloads a large file to target_path in streaming fashion.

    Writes to a .part file first and only renames it after the download
    completes fully. An aborted run therefore leaves behind no half file that
    the existence check would wrongly count as finished.
    """
    if already_fetched(target_path) and not refresh:
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = target_path.with_suffix(target_path.suffix + ".part")

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, headers=config.HTTP_HEADERS, timeout=timeout) as response:
                if response.status_code in config.HTTP_RETRY_STATUS:
                    last_error = requests.HTTPError(f"transient status {response.status_code} for {url}")
                else:
                    response.raise_for_status()
                    with part_path.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1 << 20):
                            handle.write(chunk)
                    part_path.replace(target_path)
                    return target_path
        except requests.RequestException as error:
            last_error = error

        time.sleep(config.HTTP_BACKOFF_FACTOR ** attempt)

    raise RuntimeError(f"download failed after {max_retries} attempts: {url}") from last_error
