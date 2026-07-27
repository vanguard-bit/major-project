from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode

import yaml

from ait.experiments.schema import ScenarioDefinition

SCHEMA_EXAMPLE_NAME = "schema.example.yaml"
PRIMARY_SUITES = frozenset({"crm", "platform"})
EXTENDED_SUITES = frozenset({"robustness", "evasion"})
ALL_SUITES = PRIMARY_SUITES | EXTENDED_SUITES
# Excluded from suite=all so Phase 5 corpora do not enter primary offline metrics.
EXCLUDED_FROM_ALL = frozenset({"robustness", "evasion"})
SKIP_DIR_NAMES = frozenset({"invalid"})
SKIP_FILE_NAMES = frozenset({"eva-malformed.yaml"})


def normalize_path(path: str) -> str:
    if "?" not in path:
        return path
    base, _, query = path.partition("?")
    pairs = parse_qsl(query, keep_blank_values=True)
    sorted_query = urlencode(sorted(pairs))
    return f"{base}?{sorted_query}" if sorted_query else base


def load_scenario(path: Path) -> ScenarioDefinition:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"scenario root must be a mapping: {path}")
    if "exchanges" in raw and isinstance(raw["exchanges"], list):
        for exchange in raw["exchanges"]:
            if isinstance(exchange, dict) and "path" in exchange:
                exchange["path"] = normalize_path(str(exchange["path"]))
    if "target" in raw and isinstance(raw["target"], dict):
        endpoints = raw["target"].get("expected_endpoints")
        if isinstance(endpoints, list):
            raw["target"]["expected_endpoints"] = [
                normalize_path(str(item)) for item in endpoints
            ]
    return ScenarioDefinition.model_validate(raw)


def _is_excluded_from_all(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in EXCLUDED_FROM_ALL for part in parts)


def discover_scenario_paths(root: Path, suite: str = "all") -> list[Path]:
    root = Path(root)
    if suite == "all":
        search_roots = [root]
    elif suite in ALL_SUITES:
        search_roots = [root / suite]
    else:
        raise ValueError(f"unsupported suite: {suite}")

    paths: list[Path] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*.yaml")):
            if path.name == SCHEMA_EXAMPLE_NAME or path.name in SKIP_FILE_NAMES:
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if suite == "all" and _is_excluded_from_all(path, root):
                continue
            paths.append(path)
    return paths


def load_scenarios(root: Path, suite: str = "all") -> list[ScenarioDefinition]:
    scenarios: list[ScenarioDefinition] = []
    seen_ids: dict[str, Path] = {}
    for path in discover_scenario_paths(root, suite=suite):
        scenario = load_scenario(path)
        if scenario.id in seen_ids:
            raise ValueError(
                f"duplicate scenario id {scenario.id!r}: {seen_ids[scenario.id]} and {path}"
            )
        if suite != "all" and scenario.suite != suite:
            raise ValueError(
                f"scenario {scenario.id} has suite {scenario.suite!r}, expected {suite!r}"
            )
        if suite == "all" and scenario.suite in EXCLUDED_FROM_ALL:
            continue
        seen_ids[scenario.id] = path
        scenarios.append(scenario)
    return scenarios
