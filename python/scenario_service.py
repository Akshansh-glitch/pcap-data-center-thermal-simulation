"""Saved scenarios contain configuration only, independent of results."""
from __future__ import annotations
import json
import re
from pathlib import Path
from .model import ROOT, validate_config

SCENARIOS = ROOT / "data" / "scenarios"


def save_scenario(name: str, config: dict, directory: Path = SCENARIOS) -> Path:
    validate_config(config)
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError("scenario needs a name")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.json"
    path.write_text(json.dumps({"name": name, "config": config}, indent=2), encoding="utf-8")
    return path


def list_scenarios(directory: Path = SCENARIOS) -> list[Path]:
    return sorted(directory.glob("*.json")) if directory.exists() else []


def load_scenario(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))["config"]
    validate_config(config)
    return config
