#!/usr/bin/env python3
"""CLI gate for CI — blocking pass/fail with process exit code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aos_validator_mcp.call_logger import log_tool_call
from aos_validator_mcp.validator import format_json_result, validate_agent


def run_gate(
    target_dir: Path,
    *,
    gate_mode: str = "blocking",
    mock: bool = False,
    tool_id: str | None = None,
    source: str = "external",
    caller: str | None = None,
) -> int:
    target_dir = target_dir.expanduser().resolve()
    if not target_dir.is_dir():
        print(f"ERROR: not a directory: {target_dir}", file=sys.stderr)
        return 2

    if tool_id:
        result = validate_agent(
            tool_id,
            target_dir=target_dir,
            gate_mode=gate_mode,  # type: ignore[arg-type]
            mock=mock,
            source=source,
        )
    else:
        result = validate_agent(
            target_dir,
            gate_mode=gate_mode,  # type: ignore[arg-type]
            mock=mock,
            source=source,
        )

    payload = json.loads(format_json_result(result))
    log_caller = caller or os.environ.get("AOS_VALIDATOR_CALLER", "ci").strip() or "ci"
    log_path = log_tool_call(
        "aos_compliance_validate",
        {
            "tool_id": result.tool_id,
            "target_dir": str(target_dir),
            "gate_mode": gate_mode,
            "mock": mock,
        },
        {
            "status": "success" if result.gate_pass else "blocked",
            "gate_pass": result.gate_pass,
            "gate_mode": result.gate_mode,
            "blocks_next_step": result.blocks_next_step,
            "aos_score": result.aos_score,
        },
        caller=log_caller,
    )

    print(f"JSONL -> {log_path}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if result.blocks_next_step else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MCP Blast-Radius Auditor — CI gate. "
            "Catch an MCP server that touches files it said it wouldn't. "
            "Default gate_mode=blocking — divergences or violations exit 1."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Target directories (default: --target-dir or .).",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Scan root (default: . when no positional paths).",
    )
    parser.add_argument(
        "--gate-mode",
        choices=("advisory", "blocking"),
        default="blocking",
        help="advisory=report only / blocking=exit 1 when pass=false (default).",
    )
    parser.add_argument(
        "--tool-id",
        default=None,
        help="Optional monorepo tool ID for lookup under target-dir.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Deterministic mock (no filesystem scan).",
    )
    parser.add_argument(
        "--source",
        default="external",
        help="JSONL source label (default: external).",
    )
    args = parser.parse_args()

    targets: list[Path] = []
    if args.paths:
        targets = [Path(p) for p in args.paths]
    elif args.target_dir is not None:
        targets = [Path(args.target_dir)]
    else:
        targets = [Path(".")]

    failures = 0
    for target in targets:
        print(
            f"=== GATE {target} ({args.gate_mode}, "
            f"caller={os.environ.get('AOS_VALIDATOR_CALLER', 'ci')}) ==="
        )
        rc = run_gate(
            target,
            gate_mode=args.gate_mode,
            mock=args.mock,
            tool_id=args.tool_id,
            source=args.source,
        )
        if rc != 0:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
