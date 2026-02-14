#!/usr/bin/env python3
"""Generate JSON Schema for profile config.yml from Ansible role argument specs.

Uses `ansible-doc -t role --json` to extract role specs and converts them
to a JSON Schema for editor integration (autocompletion, validation, hover docs).

Usage:
    mise x -- uv run python scripts/generate_config_schema.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"
OUTPUT_FILE = PROJECT_ROOT / "schemas" / "config.schema.json"

# Ansible type -> JSON Schema type mapping
TYPE_MAP: dict[str, dict] = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "bool": {"type": "boolean"},
    "float": {"type": "number"},
    "path": {"type": "string"},
    "dict": {"type": "object"},
    "raw": {},
}


def convert_option(name: str, spec: dict) -> dict:
    """Convert a single Ansible option spec to JSON Schema."""
    ansible_type = spec.get("type", "str")
    schema: dict = {}

    # Description
    desc = spec.get("description")
    if desc:
        if isinstance(desc, list):
            desc = "\n".join(desc)
        schema["description"] = desc.strip()

    # Handle list type
    if ansible_type == "list":
        schema["type"] = "array"
        elements = spec.get("elements", "str")
        if elements == "dict" and spec.get("options"):
            schema["items"] = convert_options_to_object(spec["options"])
        elif elements in TYPE_MAP:
            schema["items"] = TYPE_MAP[elements].copy()
        else:
            schema["items"] = {}
    elif ansible_type in TYPE_MAP:
        schema.update(TYPE_MAP[ansible_type])
    # Unknown type — leave as any

    # Choices -> enum
    if "choices" in spec:
        schema["enum"] = spec["choices"]

    # Default value (skip Jinja2 templates)
    if "default" in spec and spec["default"] is not None:
        default = spec["default"]
        if not isinstance(default, str) or "{{" not in default:
            schema["default"] = default

    return schema


def convert_options_to_object(options: dict) -> dict:
    """Convert Ansible options dict to a JSON Schema object."""
    properties = {}
    required = []

    for opt_name, opt_spec in options.items():
        properties[opt_name] = convert_option(opt_name, opt_spec)
        if opt_spec.get("required"):
            required.append(opt_name)

    result: dict = {"type": "object", "properties": properties}
    if required:
        result["required"] = sorted(required)
    result["additionalProperties"] = False
    return result


def extract_specs_via_ansible_doc(role_names: list[str]) -> dict:
    """Run ansible-doc to get role specs as JSON."""
    cmd = [
        "ansible-doc",
        "-t",
        "role",
        "--json",
        "--roles-path",
        str(ROLES_DIR),
        *role_names,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(
            f"Warning: ansible-doc exited with code {result.returncode}",
            file=sys.stderr,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    return json.loads(result.stdout)


def build_schema() -> dict:
    """Build the complete JSON Schema from all role specs."""
    # Discover roles
    role_names = sorted(
        d.name for d in ROLES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    print(f"Extracting specs from {len(role_names)} roles: {', '.join(role_names)}")
    all_specs = extract_specs_via_ansible_doc(role_names)

    # Merge all role options into top-level properties
    properties: dict = {}
    seen_vars: dict[
        str, str
    ] = {}  # variable_name -> role_name (for duplicate detection)

    for role_name in role_names:
        role_data = all_specs.get(role_name, {})
        entry_points = role_data.get("entry_points", {})
        main = entry_points.get("main", {})
        options = main.get("options")
        if not options:
            print(f"  {role_name}: no options (skipping)")
            continue

        print(f"  {role_name}: {len(options)} option(s)")
        for var_name, var_spec in options.items():
            if var_name in seen_vars:
                print(
                    f"  WARNING: duplicate variable '{var_name}' "
                    f"in roles '{seen_vars[var_name]}' and '{role_name}'",
                    file=sys.stderr,
                )
            seen_vars[var_name] = role_name
            properties[var_name] = convert_option(var_name, var_spec)

    # Add special 'profile' key (not from any role — it's consumed by the inventory plugin)
    properties["profile"] = {
        "description": "Profile configuration for the dynamic inventory plugin",
        "type": "object",
        "properties": {
            "name": {
                "description": "Profile name (must match directory name)",
                "type": "string",
            },
            "priority": {
                "description": "Profile priority (lower runs first)",
                "type": "integer",
            },
            "host": {
                "description": "Ansible host name (defaults to profile name)",
                "type": "string",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Dotfiles Profile Configuration",
        "description": "Configuration schema for dotfiles profile config.yml files",
        "type": "object",
        "properties": dict(sorted(properties.items())),
        "additionalProperties": True,
    }

    print(f"\nGenerated schema with {len(properties)} properties")
    return schema


def main() -> None:
    schema = build_schema()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    print(f"Schema written to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
