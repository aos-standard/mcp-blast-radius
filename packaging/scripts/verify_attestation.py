#!/usr/bin/env python3
"""Independently verify an AOS audit badge attestation (Ed25519 + expiry)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from attestation_common import evidence_hash, load_public_key, verify_payload


def _load_json_source(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source) as resp:
            return json.loads(resp.read().decode("utf-8"))
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Attestation not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _check_expiry(payload: dict) -> tuple[bool, str]:
    raw = payload.get("expires_at")
    if not raw:
        return False, "missing expires_at"
    try:
        expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False, f"invalid expires_at: {raw}"
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if now > expires:
        return False, f"expired at {expires.isoformat()}"
    return True, f"valid until {expires.isoformat()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify signed audit attestation JSON.")
    parser.add_argument(
        "attestation",
        help="Path or HTTPS URL to attestation JSON",
    )
    parser.add_argument(
        "--public-key",
        help="PEM public key path or HTTPS URL (default: AOS_PUBLIC_KEY_PATH env)",
    )
    args = parser.parse_args()

    try:
        payload = _load_json_source(args.attestation)
        public_key = load_public_key(args.public_key)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    digest = evidence_hash(payload)
    stored = payload.get("evidence_hash")
    if stored != digest:
        print(f"FAIL: evidence_hash mismatch (stored={stored}, computed={digest})", file=sys.stderr)
        return 1

    try:
        if not verify_payload(payload, public_key):
            print("FAIL: Ed25519 signature verification failed", file=sys.stderr)
            return 1
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    ok, expiry_msg = _check_expiry(payload)
    if not ok:
        print(f"FAIL: {expiry_msg}", file=sys.stderr)
        return 1

    print("PASS: Ed25519 signature valid")
    print(f"PASS: {expiry_msg}")
    print(f"tool_repo: {payload.get('tool_repo')}")
    print(f"scanned_version: {payload.get('scanned_version')}")
    summary = payload.get("result_summary") or {}
    print(
        f"result: gate_pass={summary.get('gate_pass')} "
        f"divergences={summary.get('divergence_count')} red={summary.get('red_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
