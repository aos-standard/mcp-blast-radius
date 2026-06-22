---
name: Blast-radius scan question
about: Share scan JSON — false positive, missed capability, or unexpected divergences
title: "[scan] "
labels:
  - question
assignees: []
---

<!-- Static surface analysis only — false positives and missed code paths are possible. -->

## Question

I scanned **\<server name or repo URL\>** and got this `blast_radius` / `divergences` JSON — **is this expected?**

Paste the JSON below (redact secrets, tokens, and local paths).

## Scan details

- **MCP server repo:** (URL or name)
- **Commit / version scanned:**
- **mcp-blast-radius version:** (e.g. `0.2.2`)

## Command

```bash
mcp-blast-radius-gate --gate-mode advisory --target-dir /path/to/server
```

## Result (JSON)

```json
(paste here)
```

## Confidence labels (in the JSON)

| Label | Meaning |
|-------|---------|
| `declared` | From manifest or dependency files |
| `observed-static` | Seen in AST / surface-level Python scan |
| `cannot-determine` | Dynamic import, native code, or obfuscation — may hide behavior |

Static analysis only — we do not claim complete coverage.

## What I expected

(One paragraph — e.g. "network import is test-only" or "README says filesystem-only")

## What would help

- [ ] False positive — static rule too aggressive
- [ ] Missed capability — code path not detected
- [ ] Manifest / divergence logic
- [ ] Docs / UX
