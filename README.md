# MCP Blast-Radius Auditor

> **See what any MCP server can actually touch — before you add it to your agent.**

No manifest? You still get the full blast-radius report. Add a manifest to also catch divergences.

> Also, if the server declares a manifest: **Catch an MCP server that touches files it said it wouldn't — and block the merge in CI.**

Statically extract what a third-party MCP server can reach (files, network, subprocess, env) via surface-level analysis. Compare against declared boundaries when a manifest is present.

## Try it in 3 steps

**1 — Install & scan**

```bash
pip install mcp-blast-radius==0.2.2
mcp-blast-radius-gate --gate-mode advisory --target-dir /path/to/mcp-server
```

**2 — Example target** (any cloned MCP repo root)

```bash
git clone --depth 1 https://github.com/oraios/serena.git /tmp/serena
mcp-blast-radius-gate --gate-mode advisory --target-dir /tmp/serena
```

**3 — Report findings** — [Open a GitHub issue](https://github.com/aos-standard/mcp-blast-radius/issues/new) with your JSON output (structured template loads automatically).

## 30-second scan

```bash
pip install mcp-blast-radius
mcp-blast-radius-gate --gate-mode blocking --target-dir /path/to/mcp-server
```

`pipx run mcp-blast-radius` starts the **MCP stdio server** (for Claude Desktop / Cursor). For CLI scanning, use `mcp-blast-radius-gate` as above.

- **Red (blocking):** divergence detected — code touches paths or capabilities not declared in manifest.
- **Green:** no divergences (or no manifest — blast radius report only, advisory pass).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## CLI entry

```bash
mcp-blast-radius          # MCP stdio server
mcp-blast-radius-gate     # CI gate (default blocking, exit 1 on fail)
```

### CI blocking gate

```bash
mcp-blast-radius-gate --gate-mode blocking --target-dir .
# no divergences → exit 0 / divergences or declaration violations → exit 1
```

## MCP tools

- `aos_compliance_validate` — scan one MCP server directory (`target_dir` required; `tool_id` optional label)
- `aos_compliance_self_test` — wiring smoke test

Default `gate_mode=advisory`. Use `gate_mode=blocking` in CI to fail on divergences.

## What is extracted

| Layer | Scope | Confidence |
|-------|-------|------------|
| Dependencies | `requirements.txt`, `pyproject.toml`, `package.json` | `declared` |
| Python AST | imports, file I/O, network, env, subprocess; MCP tool attribution | `observed-static` / `cannot-determine` |
| Divergence | manifest `permitted_output_paths` / `oracle_paths` vs observed access | blocking when mismatch |

**Limitations:** Static analysis only. Dynamic imports, `getattr`/`eval`, obfuscation, and native extensions may hide capabilities. We do not claim complete coverage — every finding includes a `confidence` label.

## Environment

| Variable | Purpose |
|----------|---------|
| `AOS_VALIDATOR_TARGET_DIR` | Default scan root when `target_dir` is omitted |
| `AOS_VALIDATOR_MCP_LOG` | JSONL path for local tool call log (never sent externally) |
| `AOS_VALIDATOR_CALLER` | Caller label (`ci`, `smoke_self_call`, etc.) |

## Example

```bash
aos_compliance_validate target_dir=/path/to/my-mcp-server gate_mode=blocking
```

## License

MIT
