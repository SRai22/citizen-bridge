from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

DEFINITIONS = Path(__file__).parent / "workflows" / "definitions"


def load_workflows(profile: Mapping[str, object]) -> list[dict[str, Any]]:
    definitions = [yaml.safe_load(path.read_text()) for path in sorted(DEFINITIONS.glob("*.yaml"))]
    applicable = [
        definition
        for definition in definitions
        if not definition.get("dynamic", False)
        and all(_matches(profile, rule) for rule in definition["applicability_rules"])
    ]
    active_ids = {definition["id"] for definition in applicable}
    for definition in applicable:
        missing = set(definition["inter_workflow_dependencies"]) - active_ids
        if missing:
            raise ValueError(
                f"Workflow '{definition['id']}' requires inactive workflow(s): "
                + ", ".join(sorted(missing))
            )
    return applicable


def _matches(profile: Mapping[str, object], rule: dict[str, Any]) -> bool:
    value: object = profile
    for segment in rule["field"].split("."):
        if not isinstance(value, Mapping) or segment not in value:
            return False
        value = value[segment]
    return type(value) is type(rule["equals"]) and value == rule["equals"]
