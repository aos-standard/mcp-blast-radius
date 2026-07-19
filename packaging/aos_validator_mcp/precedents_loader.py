"""Load bundled precedent index and full-text bodies (phone-home free)."""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path
from typing import Any

CHAIN_TYPE_INPUT = "input"
CHAIN_TYPE_APPROVAL = "approval"
CHAIN_TYPE_EVIDENCE = "evidence"
CHAIN_TYPE_RECONCILIATION = "reconciliation"
CHAIN_TYPE_POSTING = "posting"
CHAIN_TYPE_NOTIFICATION = "notification"

CHAIN_TYPES = frozenset(
    {
        CHAIN_TYPE_INPUT,
        CHAIN_TYPE_APPROVAL,
        CHAIN_TYPE_EVIDENCE,
        CHAIN_TYPE_RECONCILIATION,
        CHAIN_TYPE_POSTING,
        CHAIN_TYPE_NOTIFICATION,
    }
)

# Template section mapping (Japanese labels -> chain_type enum).
DNA_CHAIN_SECTION_MAP: dict[str, str] = {
    "input": CHAIN_TYPE_INPUT,
    "approval": CHAIN_TYPE_APPROVAL,
    "evidence": CHAIN_TYPE_EVIDENCE,
    "reconciliation": CHAIN_TYPE_RECONCILIATION,
    "posting": CHAIN_TYPE_POSTING,
    "notification": CHAIN_TYPE_NOTIFICATION,
}


def _dev_precedents_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "precedents"


def _resource_precedents_dir() -> Path | None:
    try:
        root = resources.files("precedents")
    except ModuleNotFoundError:
        return None
    with resources.as_file(root) as path:
        resolved = Path(path)
        if resolved.is_dir():
            return resolved
    return None


def precedents_dir() -> Path:
    dev_dir = _dev_precedents_dir()
    if dev_dir.is_dir() and (dev_dir / "index.json").is_file():
        return dev_dir
    resource_dir = _resource_precedents_dir()
    if resource_dir is not None and (resource_dir / "index.json").is_file():
        return resource_dir
    return dev_dir


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _index_path() -> Path:
    return precedents_dir() / "index.json"


def _body_path(precedent_id: str) -> Path:
    return precedents_dir() / f"{precedent_id}.json"


def load_index() -> list[dict[str, Any]]:
    path = _index_path()
    if not path.is_file():
        raise FileNotFoundError(f"missing bundled index: {path}")
    data = _load_json(path)
    entries = data.get("entries")
    if isinstance(entries, list):
        return [e for e in entries if isinstance(e, dict)]
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    raise ValueError(f"invalid index shape: {path}")


def list_entries() -> list[dict[str, Any]]:
    return list(load_index())


def get_entry(precedent_id: str) -> dict[str, Any] | None:
    for entry in load_index():
        if entry.get("precedent_id") == precedent_id:
            return entry
    return None


def get_body(precedent_id: str) -> dict[str, Any] | None:
    path = _body_path(precedent_id)
    if not path.is_file():
        return None
    body = _load_json(path)
    if body.get("precedent_id") != precedent_id:
        return None
    return body


def search_by_chain(chain_type: str) -> list[str]:
    if chain_type not in CHAIN_TYPES:
        return []
    matched: list[str] = []
    for entry in load_index():
        raw_types = entry.get("chain_types")
        if not isinstance(raw_types, list):
            continue
        if chain_type in raw_types:
            pid = entry.get("precedent_id")
            if isinstance(pid, str):
                matched.append(pid)
    return sorted(matched)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
