from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from artifactor.io import write_json

from .adapters import prepare_cptac_ccrcc, prepare_seqc2
from .contracts import PreparationManifest
from .operations import Tier, _digest, records_for_tier, verify_dataset
from .registry import dataset_entry


def _commit() -> str | None:
    executable = shutil.which("git")
    if executable is None:
        candidate = Path("C:/Program Files/Git/cmd/git.exe")
        executable = str(candidate) if candidate.exists() else None
    if executable is None:
        return None
    try:
        return subprocess.check_output([executable, "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def prepare_dataset(dataset_id: str, tier: Tier, data_root: Path) -> Path:
    status = verify_dataset(dataset_id, tier, data_root)
    if not status.verified:
        raise ValueError(f"source inputs are not verified: missing={status.missing_files}, mismatches={status.checksum_mismatches}")
    entry = dataset_entry(dataset_id)
    source = data_root / "source" / dataset_id / entry.release_or_snapshot
    frozen = {item.file_name: item.checksum for item in records_for_tier(dataset_id, tier)}
    fingerprint_payload = {"dataset_id": dataset_id, "tier": tier, "snapshot": entry.release_or_snapshot, "preparation_version": entry.preparation_version, "sources": frozen}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()[:16]
    destination = data_root / "prepared" / dataset_id / fingerprint
    if (destination / "preparation_manifest.json").exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix=f".{fingerprint}-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        if entry.adapter == "seqc2":
            ledger, warnings = prepare_seqc2(source, staging)
        else:
            ledger, warnings = prepare_cptac_ccrcc(source, staging)
        write_json([item.model_dump(mode="json") for item in ledger], staging / "transformation_ledger.json")
        provenance = {"schema_version": "4.0", "dataset_id": dataset_id, "source_snapshot": entry.release_or_snapshot, "source_records": [item.model_dump(mode="json") for item in records_for_tier(dataset_id, tier)], "access_terms": entry.license_or_terms, "adapter": entry.adapter, "preparation_version": entry.preparation_version}
        write_json(provenance, staging / "source_provenance.json")
        (staging / "config.yaml").write_text(yaml.safe_dump({"schema_version": "4.0", "dataset_id": dataset_id, "tier": tier, "prepared_root": ".", "immutable_source_root": str(source.resolve()), "normalization_state": "upstream ComBat-adjusted" if dataset_id == "cptac_ccrcc" else "submitted calls unchanged"}, sort_keys=True), encoding="utf-8")
        output_checksums = {item.name: _digest(item, "sha256") for item in sorted(staging.iterdir()) if item.is_file()}
        manifest = PreparationManifest(dataset_id=dataset_id, source_snapshot=entry.release_or_snapshot, preparation_version=entry.preparation_version, preparation_fingerprint=fingerprint, start_timestamp=started, completion_timestamp=datetime.now(UTC), source_checksums=frozen, code_commit=_commit(), container_digest=None, dependency_versions={name: importlib.metadata.version(name) for name in ["pandas", "pyarrow", "pydantic", "openpyxl"]}, parameters={"tier": tier, "no_silent_inference": True}, row_counts_before_after={item.step_id: {"before": item.rows_in, "after": item.rows_out} for item in ledger}, exclusions=[{"scope": "seqc2_primary", "reason": "AIS excluded from original four-sample primary comparison"}] if dataset_id == "seqc2_oncopanel" else [], warnings=warnings, output_checksums=output_checksums)
        write_json(manifest.model_dump(mode="json"), staging / "preparation_manifest.json")
        os.replace(staging, destination)
    return destination
