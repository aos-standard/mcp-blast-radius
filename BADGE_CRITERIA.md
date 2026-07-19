# AOS Audit Badge Criteria

**Program:** `aos-audited` — a signed, opt-in attestation that you ran [mcp-blast-radius](https://github.com/aos-standard/mcp-blast-radius) on your MCP server and passed human review of the machine output.

**Free. No phone-home. No paid tier.**

---

## How it works

1. **You run the scan** on your own machine (we never actively scan your repo).
2. **You apply** via the [badge application issue template](https://github.com/aos-standard/mcp-blast-radius/issues/new?template=badge-application.yml).
3. **We review** the pasted JSON only — no personality scoring, no reputation gate.
4. **If approved**, we publish a signed attestation in [aos-standard/catalog](https://github.com/aos-standard/catalog/tree/main/attestations) and send you a README snippet.

Badges expire **90 days** after issue. Re-apply with a fresh scan anytime.

---

## Review method (methodology, not exposure)

Review is **methodology-first and aggregate in tone**:

- We classify findings against **73 calibration pattern classes** built from our own fleet scans (counts and categories only — the corpus body stays private).
- We do **not** publish individual vulnerability narratives or maintainer scores.
- We do **not** claim malicious intent — undeclared capability ≠ malice; it means unauditable drift.
- Static analysis only: treat reported network/subprocess/env surface as **upper bounds**, not confirmed runtime traffic.

This matches how we report our own audits: aggregate divergence classes, not a hit list of third-party servers.

---

## What we check in your scan JSON

| Check | Meaning |
|-------|---------|
| `gate_pass` in advisory mode | Scan completed; blocking-mode failures are explained in review |
| Divergence count | Declared vs. observed mismatches (if you ship a manifest) |
| Scan scope | Production package path (`src/`, package root) — not tests/docs unless you declare otherwise |
| Tool version | Matches a published PyPI release |

We **do not** require zero divergences for every repo. Many honest MCP servers show undeclared dependency surface. The badge means: *you ran the tool, we verified the output, and the attestation is signed and dated.*

---

## What we never do

- Active scanning without your issue application (opt-in violation)
- Charging for badges (no monetization — catalog SKUs are separate)
- Phone-home or telemetry in badge display (static JSON / shields.io endpoint only)
- Publishing unsigned attestations (Ed25519 signature; verify with [attestations/README](https://github.com/aos-standard/catalog/blob/main/attestations/README.md))

---

## Verify any badge

1. Open the attestation JSON linked from the badge (catalog `attestations/{owner}__{repo}.json`).
2. Check `expires_at` is in the future.
3. Run independent verification (requires [cryptography](https://pypi.org/project/cryptography/)):

```bash
pip install cryptography
git clone --depth 1 https://github.com/aos-standard/mcp-blast-radius.git
cd mcp-blast-radius/packaging/scripts
python3 verify_attestation.py \
  https://raw.githubusercontent.com/aos-standard/catalog/main/attestations/OWNER__REPO.json \
  --public-key https://raw.githubusercontent.com/aos-standard/catalog/main/attestations/public_key.pem
```

Public key: [catalog/attestations/public_key.pem](https://raw.githubusercontent.com/aos-standard/catalog/main/attestations/public_key.pem)

---

## Static SVG alternative

Prefer no shields.io dependency? Copy the markdown snippet from your attestation `snippet` field, or use a plain link to your attestation JSON.

---

## Related

- [Try it in 3 steps (README)](README.md#try-it-in-3-steps)
- [Catalog](https://github.com/aos-standard/catalog)
- [AOS spec](https://github.com/aos-standard/AOS-spec)
