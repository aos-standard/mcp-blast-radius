#!/usr/bin/env python3
"""Sync packaging/precedents index from Vault metadata (no auto-translation)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_PACKAGING = Path(__file__).resolve().parents[1]
_TOOL_ROOT = _PACKAGING.parent
_DEV_ROOT = _TOOL_ROOT.parents[4]

sys.path.insert(0, str(_PACKAGING))

from aos_validator_mcp.precedents_loader import sha256_file  # noqa: E402

_FORBIDDEN_RE = re.compile(
    r"帝國|帝国|九一式|Type ?91|Imperial|主権者|Vault|聖典|蹂躙|"
    r"04_Knowledge|02_Production|shared\.Core|"
    r"\bPhase\s*[0-9]|0061|vitals_engine|Tetsuroh|判例",
    re.IGNORECASE,
)

OLD_PREC_EXCLUDE_RE = re.compile(r"PREC_0\d{3,}")
PREC_DNA_ID_RE = re.compile(r"^PREC_DNA-\d+$")
CONFIDENTIALITY_KEY = "confidentiality_check"


def _load_public_meta(dev_root: Path) -> dict[str, dict]:
    meta_path = (
        dev_root
        / "02_Production"
        / "A0000-A0999"
        / "A0000-A0099"
        / "0012_Public_Catalog_Publisher"
        / "config"
        / "precedents_public.json"
    )
    if not meta_path.is_file():
        raise SystemExit(f"ERROR: missing precedents_public.json: {meta_path}")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("ERROR: precedents_public.json must be a JSON object")
    return data


def _vault_dir(dev_root: Path) -> Path:
    return (
        dev_root
        / "04_Knowledge"
        / "00_Tetsuroh_Vault"
        / "10_Intellect"
        / "04_Precedents"
    )


def _extract_precedent_id(filename: str) -> str | None:
    match = re.search(r"PREC_DNA-(\d+)", filename)
    if not match:
        return None
    return f"PREC_DNA-{match.group(1)}"


def _extract_date(filename: str) -> str | None:
    match = re.match(r"^(\d{4})(\d{2})(\d{2})_", filename)
    if not match:
        return None
    y, m, d = match.groups()
    return f"{y}-{m}-{d}"


def _parse_frontmatter(md_path: Path) -> dict[str, str]:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end].strip()
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip()
    return out


def _forbidden_hits(path: Path) -> list[str]:
    hits: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FORBIDDEN_RE.search(line):
            hits.append(f"{path}:{lineno}:{line.strip()}")
    return hits


def _chain_types_for_id(precedent_id: str) -> list[str]:
    if precedent_id == "PREC_DNA-0001":
        return ["evidence", "posting"]
    return []


def _business_dna_label(precedent_id: str) -> str:
    if precedent_id == "PREC_DNA-0001":
        return "evidence-processing chain"
    return "business-dna chain"


def _artifact_root_hash(frontmatter: dict[str, str]) -> str | None:
    anchor = frontmatter.get("anchor")
    if isinstance(anchor, str) and "artifact_root_hash:" in anchor:
        # YAML inline anchor block not parsed — read nested keys from raw file instead.
        pass
    raw_hash = frontmatter.get("artifact_root_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip()
    for key, val in frontmatter.items():
        if key == "anchor" and "artifact_root_hash" in val:
            continue
    text = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    match = re.search(r"artifact_root_hash:\s*([0-9a-f]{64})", text)
    if match:
        return match.group(1)
    return None


def _ira_sig(frontmatter: dict[str, str]) -> str | None:
    sig = frontmatter.get("ira_sig_nonce") or frontmatter.get("ira_sig")
    if isinstance(sig, str) and sig.strip() and not sig.startswith("【"):
        return sig.strip()
    return None


def discover_dna_files(vault: Path) -> list[Path]:
    if not vault.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(vault.glob("*.md")):
        if OLD_PREC_EXCLUDE_RE.search(path.name):
            continue
        pid = _extract_precedent_id(path.name)
        if pid and PREC_DNA_ID_RE.match(pid):
            files.append(path)
    return files


def sync_bundle(dev_root: Path, *, packaging_dir: Path | None = None) -> Path:
    pack = packaging_dir or _PACKAGING
    precedents_dir = pack / "precedents"
    precedents_dir.mkdir(parents=True, exist_ok=True)

    public_meta = _load_public_meta(dev_root)
    vault = _vault_dir(dev_root)
    entries: list[dict] = []

    for md_path in discover_dna_files(vault):
        precedent_id = _extract_precedent_id(md_path.name)
        if precedent_id is None:
            continue
        frontmatter = _parse_frontmatter(md_path)
        if CONFIDENTIALITY_KEY not in frontmatter:
            raise SystemExit(
                f"ERROR: missing {CONFIDENTIALITY_KEY} in frontmatter: {md_path.name}"
            )

        meta = public_meta.get(precedent_id)
        if not isinstance(meta, dict):
            raise SystemExit(f"ERROR: missing public metadata for {precedent_id}")

        body_path = precedents_dir / f"{precedent_id}.json"
        if not body_path.is_file():
            raise SystemExit(
                f"ERROR: bundled body JSON must exist (no auto-translation): {body_path}"
            )

        forbidden = _forbidden_hits(body_path)
        if forbidden:
            raise SystemExit(
                "ERROR: forbidden terms in body JSON:\n" + "\n".join(forbidden[:20])
            )

        date_str = _extract_date(md_path.name)
        if date_str is None:
            raise SystemExit(f"ERROR: cannot parse date from {md_path.name}")

        title = meta.get("title")
        abstract = meta.get("abstract")
        if not isinstance(title, str) or not isinstance(abstract, str):
            raise SystemExit(f"ERROR: invalid title/abstract for {precedent_id}")

        fm_text = md_path.read_text(encoding="utf-8")
        artifact_hash = None
        match = re.search(r"artifact_root_hash:\s*([0-9a-f]{64})", fm_text)
        if match:
            artifact_hash = match.group(1)

        ira_sig = _ira_sig(frontmatter)
        if ira_sig is None:
            match_sig = re.search(
                r"ira_sig_nonce:\s*(IRA-SIG-[0-9a-f\-]+)", fm_text
            )
            if match_sig:
                ira_sig = match_sig.group(1)

        entries.append(
            {
                "precedent_id": precedent_id,
                "date": date_str,
                "title": title.strip(),
                "abstract": abstract.strip(),
                "business_dna_label": _business_dna_label(precedent_id),
                "chain_types": _chain_types_for_id(precedent_id),
                "estimated_market_value": 0,
                "artifact_root_hash": artifact_hash,
                "ira_sig": ira_sig,
                "sha256_bundle_body": sha256_file(body_path),
                "spec": "https://github.com/aos-standard/AOS-spec",
            }
        )

    entries.sort(key=lambda e: str(e.get("precedent_id", "")))
    index_path = precedents_dir / "index.json"
    index_path.write_text(
        json.dumps({"entries": entries}, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    for hit in _forbidden_hits(index_path):
        raise SystemExit(f"ERROR: forbidden term in index: {hit}")

    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync packaging/precedents bundle index.")
    parser.add_argument(
        "--dev-root",
        type=Path,
        default=_DEV_ROOT,
        help="Repository root (default: auto-detect)",
    )
    parser.add_argument(
        "--packaging-dir",
        type=Path,
        default=_PACKAGING,
        help="1067 packaging directory",
    )
    args = parser.parse_args()
    index_path = sync_bundle(args.dev_root.resolve(), packaging_dir=args.packaging_dir.resolve())
    print(f"OK: wrote {index_path} ({index_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
