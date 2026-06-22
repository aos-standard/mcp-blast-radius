#!/usr/bin/env python3
"""
MCP Blast-Radius Auditor — FastMCP stdio server (external distribution).

Extract blast radius and detect declaration divergences for MCP servers.
Default gate_mode=advisory (information only). Use gate_mode=blocking to enforce.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from aos_validator_mcp.call_logger import log_tool_call
from aos_validator_mcp.validator import validate_agent

mcp = FastMCP(
    "aos_compliance_validator",
    instructions=(
        "MCP Blast-Radius Auditor — see what any MCP server can actually touch "
        "(surface static analysis; no manifest required for blast-radius report). "
        "With a manifest, also detect declaration divergences. Default advisory mode "
        "returns judgment without blocking. Set gate_mode=blocking to reject merges "
        "when divergences exist."
    ),
    json_response=True,
)


def _resolve_target_dir(target_dir: str | None) -> Path:
    raw = (target_dir or os.environ.get("AOS_VALIDATOR_TARGET_DIR") or ".").strip()
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"target_dir is not a directory: {path}")
    return path


@mcp.tool()
def aos_compliance_validate(
    tool_id: str | None = None,
    target_dir: str | None = None,
    gate_mode: Literal["advisory", "blocking"] = "advisory",
    mock: bool = False,
) -> dict[str, Any]:
    """
    Validate one agent directory and return pass/fail with blocking_reasons.

    gate_mode=advisory (default): returns pass/fail info, does NOT block next steps.
    gate_mode=blocking: pass=false sets blocks_next_step=true for CI enforcement.
    """
    root = _resolve_target_dir(target_dir)
    if tool_id:
        result = validate_agent(
            tool_id,
            target_dir=root,
            gate_mode=gate_mode,
            mock=mock,
            source="dogfood",
        )
    else:
        result = validate_agent(
            root,
            gate_mode=gate_mode,
            mock=mock,
            source="external",
        )
    payload: dict[str, Any] = {
        "status": "success",
        "pass": result.gate_pass,
        "gate_pass": result.gate_pass,
        "gate_mode": result.gate_mode,
        "blocks_next_step": result.blocks_next_step,
        "aos_score": result.aos_score,
        "tool_id": result.tool_id,
        "target_dir": str(root),
        "target_path": result.target_path,
        "sections": result.sections,
        "blocking_reasons": result.blocking_reasons,
        "oracle_violations": result.oracle_violations,
        "permitted_violations": result.permitted_violations,
        "remediation": result.remediation,
        "blast_radius": result.blast_radius,
        "divergences": result.divergences,
        "scanned_at": result.scanned_at,
    }
    log_tool_call(
        "aos_compliance_validate",
        {
            "tool_id": tool_id,
            "target_dir": str(root),
            "gate_mode": gate_mode,
            "mock": mock,
        },
        payload,
    )
    return payload


@mcp.tool()
def aos_compliance_self_test(mock: bool = True) -> dict[str, Any]:
    """Self-connectivity check for MCP wiring."""
    root = _resolve_target_dir(None)
    result = validate_agent("1067", target_dir=root, gate_mode="advisory", mock=mock)
    payload: dict[str, Any] = {
        "status": "success",
        "message": "self_test_ok",
        "pass": result.gate_pass,
        "gate_mode": "advisory",
        "blocks_next_step": False,
    }
    log_tool_call("aos_compliance_self_test", {"mock": mock, "gate_mode": "advisory"}, payload)
    return payload


def main() -> None:
    import sys

    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(
            "usage: mcp-blast-radius [-h]\n\n"
            "MCP Blast-Radius Auditor (stdio transport).\n"
            "See what any MCP server can actually touch — before you add it to your agent.\n"
            "No manifest? You still get the full blast-radius report.\n"
            "With a manifest, also catches declaration divergences and blocks CI merges.\n\n"
            "Environment:\n"
            "  AOS_VALIDATOR_TARGET_DIR   default scan root\n"
            "  AOS_VALIDATOR_MCP_LOG      local JSONL log path (never sent externally)\n"
            "  AOS_VALIDATOR_MCP_TRANSPORT  stdio (default)\n"
        )
        raise SystemExit(0)

    transport = os.environ.get("AOS_VALIDATOR_MCP_TRANSPORT", "stdio").strip().lower()
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
