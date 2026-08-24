from __future__ import annotations

from pathlib import Path

import yaml

from .contracts import DatasetEntry, DatasetRegistry


def default_registry_path() -> Path:
    packaged = Path(__file__).with_name("registry.yaml")
    return packaged if packaged.exists() else Path(__file__).resolve().parents[2] / "datasets" / "registry.yaml"


def load_registry(path: Path | None = None) -> DatasetRegistry:
    source = path or default_registry_path()
    return DatasetRegistry.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))


def dataset_entry(dataset_id: str, path: Path | None = None) -> DatasetEntry:
    registry = load_registry(path)
    matches = [item for item in registry.datasets if item.dataset_id == dataset_id]
    if not matches:
        available = ", ".join(item.dataset_id for item in registry.datasets)
        raise ValueError(f"unknown dataset {dataset_id!r}; available datasets: {available}")
    return matches[0]
