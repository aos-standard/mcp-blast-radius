"""Shared helpers for AOS audit badge attestations (governance.json-aligned schema)."""

from __future__ import annotations

import os
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

GOVERNANCE_SCHEMA_VERSION = "1.0.0"
PUBLISHER = "aos-standard"
SPEC_URL = "https://github.com/aos-standard/AOS-spec"
VALIDATOR_CATALOG_ENTRY = (
    "https://raw.githubusercontent.com/aos-standard/catalog/main/catalog.json"
)
CORPUS_PATTERNS_BASE = 73
ATTESTATION_TTL_DAYS = 90


def _nonce_engine_root() -> Path:
    """Resolve signing module root (maintainer signing only; not used for verification)."""
    env = os.environ.get("AOS_NONCE_ENGINE_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError(
                f"AOS_NONCE_ENGINE_ROOT is not a directory: {root}. "
                "Signing is maintainer-only; use verify_attestation.py for independent checks."
            )
        return root
    prod = Path(__file__).resolve().parents[5]
    matches = sorted(prod.glob("A0000-A0999/A0000-A0099/0039_*"))
    if not matches:
        raise RuntimeError(
            "Ed25519 signing module not found. "
            "Set AOS_NONCE_ENGINE_ROOT for attestation issuance (maintainer use only)."
        )
    return matches[0]


def _import_nonce_engine():
    root = str(_nonce_engine_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from core.nonce_engine import NonceEngine, get_public_key_pem

    return NonceEngine, get_public_key_pem


def canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON for evidence_hash (signature fields excluded)."""
    body = {k: v for k, v in payload.items() if k not in {"signature", "evidence_hash", "snippet"}}
    return json.dumps(body, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def evidence_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def parse_github_repo(tool_url: str) -> tuple[str, str]:
    url = tool_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        raise ValueError(f"invalid GitHub repo URL: {tool_url}")
    return parts[0], parts[1]


def attestation_filename(owner: str, repo: str) -> str:
    return f"{owner}__{repo}.json"


def summarize_scan(scan: dict[str, Any]) -> dict[str, Any]:
    blocking = scan.get("blocking_reasons") or []
    divergences = [b for b in blocking if str(b).startswith("DIVERGENCE")]
    other = [b for b in blocking if not str(b).startswith("DIVERGENCE")]
    return {
        "gate_pass": bool(scan.get("gate_pass")),
        "gate_mode": scan.get("gate_mode", "advisory"),
        "red_count": len(other),
        "yellow_count": 0,
        "divergence_count": len(divergences),
    }


def build_attestation_payload(
    *,
    tool_url: str,
    scanned_version: str,
    scan_date: str,
    scan_command: str,
    scanned_path: str,
    scan: dict[str, Any],
    expires_at: str | None = None,
) -> dict[str, Any]:
    owner, repo = parse_github_repo(tool_url)
    result = summarize_scan(scan)
    verified_at = scan.get("scanned_at") or scan_date
    if expires_at is None:
        issued = datetime.fromisoformat(scan_date.replace("Z", "+00:00"))
        expires_at = (issued + timedelta(days=ATTESTATION_TTL_DAYS)).isoformat()

    return {
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "attestation_type": "mcp-blast-radius-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publisher": PUBLISHER,
        "spec": SPEC_URL,
        "structure_audit": {
            "method": "mcp-blast-radius static scan (advisory mode, maintainer-run)",
            "scopes_scanned": 1,
            "red_alerts": result["red_count"],
            "verified_at": verified_at,
        },
        "immune_loop": {
            "enabled": False,
            "mode": "n/a",
            "description": (
                "Single opt-in maintainer scan attestation; "
                "no automated purge loop attached to badge display."
            ),
            "purge_plan_records": 0,
        },
        "manifest_discipline": {
            "zone_declarations": True,
            "validator": "mcp-blast-radius",
            "validator_catalog_entry": VALIDATOR_CATALOG_ENTRY,
        },
        "knowledge_base": {
            "curated_records": CORPUS_PATTERNS_BASE,
            "note": (
                "Human review uses 73 calibration pattern classes "
                "(counts and categories only; corpus body not published)."
            ),
        },
        "tool_url": tool_url,
        "tool_repo": f"{owner}/{repo}",
        "scanned_path": scanned_path,
        "scanned_version": scanned_version,
        "scan_date": scan_date,
        "scan_command": scan_command,
        "result_summary": result,
        "corpus_patterns_base": CORPUS_PATTERNS_BASE,
        "expires_at": expires_at,
    }


def shields_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["result_summary"]
    version = payload["scanned_version"]
    if summary["gate_pass"] and summary["divergence_count"] == 0:
        color = "brightgreen"
        message = f"pass · {version}"
    elif summary["gate_pass"]:
        color = "yellow"
        message = f"advisory · {version}"
    else:
        color = "lightgrey"
        message = f"review · {version}"
    return {
        "schemaVersion": 1,
        "label": "AOS audited",
        "message": message,
        "color": color,
    }


def badge_snippet(owner: str, repo: str) -> str:
    endpoint = (
        "https://raw.githubusercontent.com/aos-standard/catalog/main/"
        f"attestations/endpoints/{owner}__{repo}.json"
    )
    criteria = "https://github.com/aos-standard/mcp-blast-radius/blob/main/BADGE_CRITERIA.md"
    return (
        f"[![AOS audited](https://img.shields.io/endpoint?url={endpoint})]({criteria})\n"
        f"<!-- Static badge — no phone-home. Verify: catalog attestations/{owner}__{repo}.json -->"
    )


def sign_payload(payload: dict[str, Any]) -> dict[str, Any]:
    NonceEngine, _ = _import_nonce_engine()
    engine = NonceEngine()
    digest = evidence_hash(payload)
    signed = dict(payload)
    signed["evidence_hash"] = digest
    signed["signature"] = engine.generate_nonce(digest)
    owner, repo = parse_github_repo(payload["tool_url"])
    signed["snippet"] = badge_snippet(owner, repo)
    return signed


def verify_payload(payload: dict[str, Any], public_key_pem: str) -> bool:
    """Verify IRA-SIG Ed25519 signature using pure cryptography (no signing module import)."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise RuntimeError(
            "cryptography is required for attestation verification. Install: pip install cryptography"
        ) from exc

    signature = payload.get("signature")
    digest = payload.get("evidence_hash")
    if not signature or not digest:
        return False
    if digest != evidence_hash(payload):
        return False

    nonce = str(signature)
    if not nonce.startswith("IRA-SIG-"):
        return False

    parts = nonce[8:].split("-", 1)
    if len(parts) != 2:
        return False

    timestamp, stored_signature_hex = parts[0], parts[1]
    if len(timestamp) != 20 or not timestamp.isdigit():
        return False
    if len(stored_signature_hex) != 128:
        return False

    try:
        stored_signature = bytes.fromhex(stored_signature_hex)
    except ValueError:
        return False

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception:
        return False

    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        return False

    message = (timestamp + str(digest).strip()).encode("utf-8")
    try:
        public_key.verify(stored_signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def _read_pem_source(source: str | Path) -> str:
    text = str(source)
    if text.startswith(("http://", "https://")):
        import urllib.request

        with urllib.request.urlopen(text) as resp:
            return resp.read().decode("utf-8")
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Public key not found: {path}")
    return path.read_text(encoding="utf-8")


def load_public_key(path: Path | str | None = None) -> str:
    if path is not None:
        return _read_pem_source(path)

    env_path = os.environ.get("AOS_PUBLIC_KEY_PATH")
    if env_path:
        return _read_pem_source(env_path)

    raise FileNotFoundError(
        "Public key not specified. Pass --public-key or set AOS_PUBLIC_KEY_PATH."
    )
