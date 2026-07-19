#!/usr/bin/env python3
"""Smoke test: external MCP fixtures pass/fail without AGENT_NOT_FOUND."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PACKAGING = Path(__file__).resolve().parents[1]
_TOOL_ROOT = _PACKAGING.parent
sys.path.insert(0, str(_TOOL_ROOT))
sys.path.insert(0, str(_PACKAGING))

from aos_validator_mcp.validator import validate_agent  # noqa: E402

_FIXTURES = _TOOL_ROOT / "tests" / "fixtures"


def main() -> int:
    good = _FIXTURES / "external_mcp_good"
    bad = _FIXTURES / "external_mcp_bad"

    good_result = validate_agent(good, gate_mode="advisory", mock=False, source="external")
    if "TARGET_NOT_FOUND" in str(good_result.blocking_reasons) or "AGENT_NOT_FOUND" in str(
        good_result.blocking_reasons
    ):
        print("FAIL: compliant external fixture returned not-found", file=sys.stderr)
        print(json.dumps(good_result.to_dict(), indent=2))
        return 1
    if not good_result.gate_pass:
        print("FAIL: compliant external fixture should pass", file=sys.stderr)
        print(json.dumps(good_result.to_dict(), indent=2))
        return 1

    bad_result = validate_agent(bad, gate_mode="advisory", mock=False, source="external")
    if "TARGET_NOT_FOUND" in str(bad_result.blocking_reasons):
        print("FAIL: non-compliant fixture returned not-found", file=sys.stderr)
        return 1
    if bad_result.gate_pass:
        print("FAIL: non-compliant fixture should fail AOS check", file=sys.stderr)
        return 1
    if not any("AOS_UNDECLARED" in r for r in bad_result.blocking_reasons):
        print("FAIL: expected AOS_UNDECLARED in blocking_reasons", file=sys.stderr)
        print(json.dumps(bad_result.to_dict(), indent=2))
        return 1

    print("OK: external fixtures pass/fail as expected")
    print(json.dumps({"good": good_result.to_dict(), "bad": bad_result.to_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
