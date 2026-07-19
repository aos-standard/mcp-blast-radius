#!/usr/bin/env python3
"""G1 self-connectivity — JSONL with gate_mode=advisory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PACKAGING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PACKAGING))

from aos_validator_mcp.call_logger import log_tool_call  # noqa: E402
from aos_validator_mcp.validator import validate_agent  # noqa: E402


def main() -> int:
    target = Path.cwd()
    result = validate_agent("1067", target_dir=target, gate_mode="advisory", mock=True)
    payload = {
        "status": "success",
        "gate_pass": result.gate_pass,
        "gate_mode": "advisory",
        "blocks_next_step": result.blocks_next_step,
        "aos_score": result.aos_score,
    }
    log_path = log_tool_call(
        "aos_compliance_validate",
        {"tool_id": "1067", "target_dir": str(target), "gate_mode": "advisory", "mock": True},
        payload,
        caller="smoke_self_call",
    )
    print(f"OK: JSONL -> {log_path}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
