"""MCP precedent query tools — list, search, get (bundled v0.1)."""

from __future__ import annotations

from typing import Any, Literal

from aos_validator_mcp.call_logger import log_tool_call
from aos_validator_mcp.precedents_loader import (
    CHAIN_TYPES,
    get_body,
    get_entry,
    list_entries,
    search_by_chain,
)

ChainType = Literal[
    "input",
    "approval",
    "evidence",
    "reconciliation",
    "posting",
    "notification",
]

PRICING_DECLARED: dict[str, Any] = {
    "model": "per_run",
    "unit_price": 1.0,
    "currency": "USD",
    "enforced": False,
}

REQUIRED_BODY_KEYS = (
    "pain",
    "facts",
    "mechanism",
    "rules",
    "implementation_requirements",
)


def _error(precedent_id: str | None, message: str, *, code: int = 404) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "code": code,
        "message": message,
        "pricing_declared": PRICING_DECLARED,
    }
    if precedent_id is not None:
        payload["precedent_id"] = precedent_id
    return payload


def _success_payload(extra: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "pricing_declared": PRICING_DECLARED, **extra}


def list_precedents() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for entry in list_entries():
        items.append(
            {
                "precedent_id": entry.get("precedent_id"),
                "business_dna_label": entry.get("business_dna_label"),
                "summary": entry.get("abstract"),
                "estimated_market_value": entry.get("estimated_market_value", 0),
                "artifact_root_hash": entry.get("artifact_root_hash"),
                "ira_sig": entry.get("ira_sig"),
            }
        )
    payload = _success_payload({"precedents": items, "count": len(items)})
    log_tool_call("list_precedents", {}, payload)
    return payload


def search_by_dna(chain_type: ChainType) -> dict[str, Any]:
    if chain_type not in CHAIN_TYPES:
        payload = _error(None, f"unknown chain_type: {chain_type}", code=400)
        log_tool_call("search_by_dna", {"chain_type": chain_type}, payload)
        return payload
    ids = search_by_chain(chain_type)
    payload = _success_payload(
        {"chain_type": chain_type, "precedent_ids": ids, "count": len(ids)}
    )
    log_tool_call("search_by_dna", {"chain_type": chain_type}, payload)
    return payload


def get_precedent(precedent_id: str) -> dict[str, Any]:
    entry = get_entry(precedent_id)
    if entry is None:
        payload = _error(precedent_id, f"precedent not found: {precedent_id}")
        log_tool_call("get_precedent", {"precedent_id": precedent_id}, payload)
        return payload

    body = get_body(precedent_id)
    if body is None:
        payload = _error(
            precedent_id,
            f"bundled body missing for: {precedent_id}",
            code=500,
        )
        log_tool_call("get_precedent", {"precedent_id": precedent_id}, payload)
        return payload

    missing = [key for key in REQUIRED_BODY_KEYS if key not in body]
    if missing:
        payload = _error(
            precedent_id,
            f"incomplete body sections: {', '.join(missing)}",
            code=500,
        )
        log_tool_call("get_precedent", {"precedent_id": precedent_id}, payload)
        return payload

    payload = _success_payload(
        {
            "precedent_id": precedent_id,
            "pain": body["pain"],
            "facts": body["facts"],
            "mechanism": body["mechanism"],
            "rules": body["rules"],
            "implementation_requirements": body["implementation_requirements"],
        }
    )
    log_tool_call("get_precedent", {"precedent_id": precedent_id}, payload)
    return payload
