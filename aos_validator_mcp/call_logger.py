"""JSONL call logger — records gate_mode on every tool invocation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _log_path() -> Path:
    env = os.environ.get("AOS_VALIDATOR_MCP_LOG", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".aos_compliance_validator" / "calls.jsonl"


def log_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    *,
    caller: str = "self",
) -> Path:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "caller": caller,
        "arguments": arguments,
        "gate_mode": arguments.get("gate_mode", result.get("gate_mode", "advisory")),
        "status": result.get("status", "unknown"),
        "pass": result.get("gate_pass", result.get("pass")),
        "blocks_next_step": result.get("blocks_next_step", False),
        "aos_score": result.get("aos_score"),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path
