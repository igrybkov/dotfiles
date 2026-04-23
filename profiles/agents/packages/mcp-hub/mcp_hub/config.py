"""Config loader — merges multiple JSON/YAML files into a unified server registry.

Sources are taken from CONFIG_FILE env var (comma-separated paths).
When unset, defaults to ~/.config/mcp-hub/servers.json and ~/.config/mcp-hub/servers.yml.
Both JSON and YAML formats are supported. Later files override earlier ones on
matching server name.

Supported server shapes:

  # stdio
  {
    "mcpServers": {
      "github": {
        "command": "gh-mcp",
        "args": ["--flag"],
        "env": {"GH_TOKEN": "..."},
        "description": "optional",
        "tags": ["optional"]
      }
    }
  }

  # streamable-http / sse
  {
    "mcpServers": {
      "ada": {
        "url": "https://ada.adobe.io/api/v2/ada/mcp",
        "transport": "streamable-http",
        "headers": {"Authorization": "..."}
      }
    }
  }

YAML files use the same shape without the outer `mcpServers` wrapper required —
top-level mapping is accepted either way.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILES = [
    "~/.config/mcp-hub/servers.json",
    "~/.config/mcp-hub/servers.yml",
]


@dataclass
class ServerSpec:
    """Unified server configuration."""

    name: str
    transport: str  # "stdio" | "streamable-http" | "sse"
    # stdio fields
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # http fields
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    # metadata
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    disabled: bool = False

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ServerSpec:
        if "url" in data:
            transport = data.get("transport", "streamable-http")
            return cls(
                name=name,
                transport=transport,
                url=data["url"],
                headers=dict(data.get("headers", {})),
                description=data.get("description"),
                tags=list(data.get("tags", [])),
                disabled=bool(data.get("disabled", False)),
            )
        return cls(
            name=name,
            transport="stdio",
            command=data.get("command"),
            args=list(data.get("args", [])),
            env=dict(data.get("env", {})),
            description=data.get("description"),
            tags=list(data.get("tags", [])),
            disabled=bool(data.get("disabled", False)),
        )


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path)))


def _load_file(path: Path) -> dict[str, Any]:
    raw = path.read_text()
    if path.suffix in (".yml", ".yaml"):
        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: top-level must be a mapping, got {type(data).__name__}"
        )
    # Accept both wrapped ({"mcpServers": {...}}) and unwrapped shapes
    if "mcpServers" in data and isinstance(data["mcpServers"], dict):
        return dict(data["mcpServers"])
    return data


def config_paths() -> list[Path]:
    """Resolve configured source paths from CONFIG_FILE env, or defaults."""
    raw = os.environ.get("CONFIG_FILE")
    sources = raw.split(",") if raw else DEFAULT_CONFIG_FILES
    return [_expand(p.strip()) for p in sources if p.strip()]


def load_servers() -> dict[str, ServerSpec]:
    """Load and merge server specs from all configured sources.

    Later sources override earlier ones by server name (shallow override).
    Missing files are skipped (logged at debug). Malformed files raise.
    """
    merged: dict[str, dict[str, Any]] = {}
    for path in config_paths():
        if not path.exists():
            logger.debug("Config file missing, skipping: %s", path)
            continue
        try:
            servers = _load_file(path)
        except Exception as e:
            logger.error("Failed to parse %s: %s", path, e)
            raise
        for name, spec in servers.items():
            if not isinstance(spec, dict):
                logger.warning("%s: skipping non-mapping entry %r", path, name)
                continue
            merged[name] = spec
        logger.info("Loaded %d server(s) from %s", len(servers), path)

    result: dict[str, ServerSpec] = {}
    for name, spec in merged.items():
        try:
            server = ServerSpec.from_dict(name, spec)
        except Exception as e:
            logger.error("Skipping invalid server spec %r: %s", name, e)
            continue
        if server.disabled:
            logger.info("Server %r is disabled — skipping", name)
            continue
        result[name] = server
    return result
