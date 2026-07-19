#!/usr/bin/env python3
"""Forbidden-term linter for external distribution surfaces."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_TOOL_ROOT = Path(__file__).resolve().parents[2]
_PACKAGING = Path(__file__).resolve().parents[1]

_FORBIDDEN_RE = re.compile(
    r"帝國|帝国|九一式|Type ?91|Imperial|主権者|Vault|聖典|蹂躙|2001|SFDC|Solana|"
    r"Messaging|tx_id|PaymentGate|VAULT_ROOT|04_Knowledge|02_Production|shared\.Core|"
    r"\bPhase\s*[0-9]|0061|vitals_engine",
    re.IGNORECASE,
)

_DEFAULT_TARGETS = [
    _PACKAGING / "aos_validator_mcp",
    _PACKAGING / "README.md",
    _PACKAGING / "pyproject.toml",
    _PACKAGING / "LICENSE",
    _TOOL_ROOT / "docs" / "USAGE.md",
    _TOOL_ROOT / "docs" / "AGENT_CARD.md",
    _TOOL_ROOT / "docs" / "guides" / "README.md",
]

_SKIP_PARTS = {"__pycache__", ".egg-info", "venv", "node_modules"}


def _scan_file(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FORBIDDEN_RE.search(line):
            hits.append((lineno, line.strip()))
    return hits


def _iter_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    files: list[Path] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if path.suffix in {".py", ".md", ".toml", ".txt", ".json"}:
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint external surfaces for forbidden internal terms.")
    parser.add_argument("paths", nargs="*", help="Additional paths to scan.")
    args = parser.parse_args()

    targets: list[Path] = list(_DEFAULT_TARGETS)
    for raw in args.paths:
        targets.append(Path(raw).expanduser().resolve())

    failures = 0
    for target in targets:
        if not target.exists():
            continue
        for file_path in _iter_files(target):
            for lineno, line in _scan_file(file_path):
                print(f"FORBIDDEN: {file_path}:{lineno}: {line}")
                failures += 1

    if failures:
        print(f"FAIL: {failures} forbidden term hit(s)", file=sys.stderr)
        return 1
    print("OK: no forbidden terms in external surfaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
