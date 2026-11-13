"""Deterministic pre-extraction for structured tool registries (design §5.5).

Ported from the former ``scanner_agent.tool_registry`` with the Finding
model dependency removed: candidates are plain dicts handed to
``StoreArtifactsTool.register_candidates``. JSON/YAML files whose item
boundaries are part of the file format must not be inferred by a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml"}
_TOOL_LIST_KEYS = ("tools", "tool_schema", "tool_schemas")


def extract_tool_candidates(
    tool_paths: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract tool candidates from unambiguous JSON/YAML registries.

    Returns ``(candidates, unresolved_paths)``. Each candidate is
    ``{"name": str, "schema": dict, "source": str}``. Unsupported, malformed,
    or ambiguous files stay in ``unresolved_paths`` for the LLM path.
    """
    candidates: list[dict[str, Any]] = []
    unresolved_paths: list[str] = []

    for raw_path in tool_paths:
        path = Path(raw_path).resolve()
        if path.suffix.lower() not in _STRUCTURED_SUFFIXES:
            unresolved_paths.append(raw_path)
            continue

        try:
            data = _load_structured_file(path)
            items = _tool_items(data)
            normalized_items = (
                [_normalize_tool_item(item) for item in items] if items is not None else None
            )
        except (OSError, ValueError, TypeError):
            normalized_items = None

        # Do not partially trust a file. If any item is ambiguous, leave the
        # whole file for the model-based extraction path.
        if normalized_items is None or any(item is None for item in normalized_items):
            unresolved_paths.append(raw_path)
            continue

        for item in normalized_items:
            if item is None:  # excluded above; keeps the type contract explicit
                continue
            name, schema = item
            candidates.append({"name": name, "schema": schema, "source": str(path)})

    return candidates, unresolved_paths


def _load_structured_file(path: Path) -> Any:
    """Load JSON/YAML without executing YAML constructors."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # Match InspectConfigLoader's Windows-friendly UTF-8/GBK behavior.
        text = path.read_text(encoding="gbk")

    if path.suffix.lower() == ".json":
        return json.loads(text)

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is a runtime dependency
        raise ValueError("PyYAML is required to parse YAML tool registries") from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # Keep malformed YAML on the LLM fallback path instead of aborting.
        raise ValueError("Invalid YAML tool registry") from exc


def _tool_items(data: Any) -> list[dict[str, Any]] | None:
    """Return list entries when the document unambiguously represents tools."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = None
        for key in _TOOL_LIST_KEYS:
            candidate = data.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None and _looks_like_tool(data):
            items = [data]
    else:
        return None

    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return None
    return items


def _looks_like_tool(item: dict[str, Any]) -> bool:
    """Avoid treating an arbitrary YAML mapping as a tool definition."""
    return any(
        key in item
        for key in (
            "name",
            "function",
            "input_schema",
            "inputSchema",
            "parameters",
            "properties",
            "module",
            "class",
        )
    )


def _normalize_tool_item(item: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Convert one supported tool item to a candidate schema object."""
    payload: Any = item
    if item.get("type") == "function":
        payload = item.get("function")
    if not isinstance(payload, dict):
        return None

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    schema: dict[str, Any] = dict(payload)

    # 1. Prefer non-empty explicit parameter containers
    parameters: Any = None
    for key in ("parameters", "inputSchema", "input_schema"):
        val = payload.get(key)
        if isinstance(val, dict) and val:
            parameters = val
            break

    # 2. Check flat schema where properties is defined at root
    if parameters is None and "properties" in payload and isinstance(payload["properties"], dict):
        parameters = {
            k: v for k, v in payload.items() if k not in ("name", "description", "function")
        }
        if "type" not in parameters:
            parameters["type"] = "object"

    # 3. Explicit container even if empty
    if parameters is None:
        for key in ("parameters", "inputSchema", "input_schema"):
            val = payload.get(key)
            if isinstance(val, dict):
                parameters = val
                break

    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return None

    schema["parameters"] = parameters
    schema.setdefault("description", "")
    if not isinstance(schema.get("description"), str):
        return None

    return name.strip(), schema


__all__ = ["extract_tool_candidates"]
