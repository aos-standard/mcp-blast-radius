# Glama MCP registry introspection (https://glama.ai/mcp/servers).
# Build from repository source — stdio MCP server, no credentials required for tools/list.

FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AOS_VALIDATOR_TARGET_DIR=/app

COPY pyproject.toml README.md LICENSE ./
COPY aos_validator_mcp ./aos_validator_mcp

RUN pip install --no-cache-dir .

COPY tests/fixtures ./tests/fixtures

RUN useradd --create-home --shell /bin/bash mcp \
    && chown -R mcp:mcp /app
USER mcp

ENTRYPOINT ["mcp-blast-radius"]
