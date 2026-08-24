from __future__ import annotations

import hashlib
import json
import os
import stat
import urllib.request
from pathlib import Path
from typing import Literal

from .contracts import AccessLevel, DatasetStatus, SourceRecord
from .registry import dataset_entry

Tier = Literal["fixture", "pilot", "full"]
LARGE_DOWNLOAD_BYTES = 500_000_000


def default_data_root() -> Path:
    configured = os.environ.get("ARTIFACTOR_DATA_ROOT")
    return Path(configured) if configured else Path.cwd() / "data"


def records_for_tier(dataset_id: str, tier: Tier) -> list[SourceRecord]:
    if tier == "fixture":
        return []
    return [item for item in dataset_entry(dataset_id).source_records if tier in item.tiers]


def expected_size(dataset_id: str, tier: Tier) -> int:
    return sum(item.size_bytes for item in records_for_tier(dataset_id, tier))


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pdc_signed_url(record: SourceRecord) -> str:
    query = (
        "{ filesPerStudy(pdc_study_id:\""
        + str(record.resolver_study_id)
        + "\" file_name:\""
        + record.file_name.replace('"', '\\"')
        + "\" offset:0 limit:5) { file_id file_name md5sum signedUrl { url } } }"
    )
    request = urllib.request.Request(
        record.authoritative_url,
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Artifactor/0.4"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        payload = json.load(response)
    files = payload.get("data", {}).get("filesPerStudy", [])
    matches = [item for item in files if item.get("file_id") == record.resolver_file_id]
    if len(matches) != 1 or not matches[0].get("signedUrl", {}).get("url"):
        raise ValueError(f"PDC did not resolve the frozen file {record.file_name}")
    if matches[0].get("md5sum") != record.checksum:
        raise ValueError(f"PDC checksum changed for {record.file_name}; registry update required")
    return str(matches[0]["signedUrl"]["url"])


def _download(record: SourceRecord, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    offset = partial.stat().st_size if partial.exists() else 0
    url = _pdc_signed_url(record) if record.resolver == "pdc_graphql" else record.authoritative_url
    headers = {"User-Agent": "Artifactor/0.4"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        append = offset > 0 and getattr(response, "status", 200) == 206
        mode = "ab" if append else "wb"
        with partial.open(mode) as output:
            while block := response.read(1024 * 1024):
                output.write(block)
    if partial.stat().st_size != record.size_bytes:
        raise ValueError(
            f"size mismatch for {record.file_name}: expected {record.size_bytes}, got {partial.stat().st_size}; retain .partial to resume or delete it to restart"
        )
    observed = _digest(partial, record.checksum_algorithm)
    if observed != record.checksum:
        raise ValueError(
            f"checksum mismatch for {record.file_name}; expected {record.checksum}, got {observed}"
        )
    os.replace(partial, destination)
    destination.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def fetch_dataset(
    dataset_id: str,
    tier: Tier,
    data_root: Path | None = None,
    confirm_large: bool = False,
) -> DatasetStatus:
    entry = dataset_entry(dataset_id)
    if entry.access_level in {AccessLevel.CONTROLLED, AccessLevel.UNAVAILABLE}:
        raise PermissionError(
            f"{dataset_id} access level is {entry.access_level.value}; default retrieval is prohibited"
        )
    records = records_for_tier(dataset_id, tier)
    size = expected_size(dataset_id, tier)
    if size >= LARGE_DOWNLOAD_BYTES and not confirm_large:
        raise ValueError(
            f"{tier} retrieval requires {size} bytes; rerun with --confirm-large after reviewing access terms and disk space"
        )
    root = data_root or default_data_root()
    destination = root / "source" / dataset_id / entry.release_or_snapshot
    destination.mkdir(parents=True, exist_ok=True)
    for record in records:
        path = destination / record.file_name
        if path.exists() and _digest(path, record.checksum_algorithm) == record.checksum:
            continue
        if path.exists():
            raise ValueError(f"existing source file has wrong checksum and will not be overwritten: {path}")
        _download(record, path)
    return dataset_status(dataset_id, tier, root)


def verify_dataset(
    dataset_id: str, tier: Tier, data_root: Path | None = None
) -> DatasetStatus:
    return dataset_status(dataset_id, tier, data_root or default_data_root())


def dataset_status(dataset_id: str, tier: Tier, data_root: Path) -> DatasetStatus:
    entry = dataset_entry(dataset_id)
    root = data_root / "source" / dataset_id / entry.release_or_snapshot
    present: list[str] = []
    missing: list[str] = []
    mismatches: list[str] = []
    for record in records_for_tier(dataset_id, tier):
        path = root / record.file_name
        if not path.exists():
            missing.append(record.file_name)
        elif _digest(path, record.checksum_algorithm) != record.checksum:
            mismatches.append(record.file_name)
        else:
            present.append(record.file_name)
    prepared_root = data_root / "prepared" / dataset_id
    prepared = (
        sorted(str(item) for item in prepared_root.iterdir() if item.is_dir())
        if prepared_root.exists()
        else []
    )
    return DatasetStatus(
        dataset_id=dataset_id,
        tier=tier,
        access_level=entry.access_level,
        expected_size_bytes=expected_size(dataset_id, tier),
        present_files=present,
        missing_files=missing,
        checksum_mismatches=mismatches,
        verified=not missing and not mismatches and bool(present or tier == "fixture"),
        prepared_directories=prepared,
    )
