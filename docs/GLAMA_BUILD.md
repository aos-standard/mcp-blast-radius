# Glama admin build configuration

Glama's default image installs Python via `uv` only — **`pip` is not on PATH**
(`pip: not found` / exit 127). Use a `uv` virtualenv instead.

## Build steps

```json
["uv venv /app/.venv", "uv pip install --python /app/.venv/bin/python --no-cache-dir ."]
```

## CMD arguments

Use the venv entrypoint (full path):

```json
["/app/.venv/bin/mcp-blast-radius"]
```

## Parameters (startup env)

```json
{}
```

## Pinned commit

Optional. Leave empty for latest `main`, or pin e.g. `0e83202`.

Then click **Build & Release**.
