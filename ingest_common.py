"""Gemeinsame Logik der Ingest-Stufe.

Dieses Modul wird nie direkt aufgerufen. Es kapselt die robuste
Datenbeschaffung (Retry mit Backoff, harte Timeouts, inkrementeller Cache,
Resume ueber Existenzpruefung) und stellt sie den schlanken Fetcher-Skripten
bereit.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

import config


def ensure_data_dirs() -> None:
    """Legt die Daten-Verzeichnisse an, falls sie fehlen."""
    for directory in (config.RAW_DIR, config.INTERIM_DIR, config.CACHE_DIR, config.ARTIFACTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def already_fetched(target_path: Path) -> bool:
    """Resume ueber Existenzpruefung: ist das Ziel schon vorhanden und nicht leer?"""
    return target_path.exists() and target_path.stat().st_size > 0


def get_with_retry(
    url: str,
    *,
    params: dict[str, str] | None = None,
    timeout: float = config.HTTP_TIMEOUT_SECONDS,
    max_retries: int = config.HTTP_MAX_RETRIES,
) -> requests.Response:
    """GET mit exponentiellem Backoff auf transiente Serverfehler.

    Transiente Fehler (429, 500, 502, 503, 504) werden mehrfach mit wachsender
    Wartezeit wiederholt. Dauerhafte Fehler (etwa 404) brechen sofort ab.
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
            last_error = requests.HTTPError(f"transienter Status {response.status_code} fuer {url}")

        wait_seconds = config.HTTP_BACKOFF_FACTOR ** attempt
        time.sleep(wait_seconds)

    raise RuntimeError(f"Abruf fehlgeschlagen nach {max_retries} Versuchen: {url}") from last_error


def download_to(url: str, target_path: Path, *, refresh: bool = False) -> Path:
    """Laedt eine kleine Datei vollstaendig nach target_path (im Speicher)."""
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
    """Laedt eine grosse Datei streamend nach target_path.

    Schreibt zuerst in eine .part-Datei und benennt erst nach vollstaendigem
    Download um. Ein abgebrochener Lauf hinterlaesst so keine halbe Datei, die
    die Existenzpruefung faelschlich als fertig zaehlt.
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
                    last_error = requests.HTTPError(f"transienter Status {response.status_code} fuer {url}")
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

    raise RuntimeError(f"Download fehlgeschlagen nach {max_retries} Versuchen: {url}") from last_error
