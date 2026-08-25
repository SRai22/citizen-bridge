import json
import unittest
from pathlib import Path

from contracts.constants.event_types import EVENT_TYPES
from contracts.constants.permissions import PERMISSIONS
from contracts.constants.roles import ROLES

CONTRACTS = Path(__file__).parents[1]


class ContractTests(unittest.TestCase):
    def test_proto_contracts_are_versioned(self) -> None:
        protos = sorted((CONTRACTS / "proto").glob("*.proto"))

        self.assertEqual(len(protos), 8)
        for proto in protos:
            source = proto.read_text()
            self.assertIn('syntax = "proto3";', source)
            self.assertIn(".v1;", source)

    def test_event_schemas_are_valid_json_schema_documents(self) -> None:
        schemas = sorted((CONTRACTS / "events").glob("*.json"))

        self.assertEqual(len(schemas), 6)
        for path in schemas:
            schema = json.loads(path.read_text())
            self.assertEqual(schema["type"], "object")
            self.assertTrue(schema["required"])
            self.assertTrue({"timestamp", "occurred_at"} & schema["properties"].keys())

    def test_constants_are_unique(self) -> None:
        self.assertEqual(ROLES, {"owner", "coordinator", "viewer"})
        self.assertEqual(
            PERMISSIONS, {"view", "submit", "approve", "manage", "delegate", "delete"}
        )
        domain = json.loads((CONTRACTS / "events/domain_event.json").read_text())
        self.assertEqual(
            EVENT_TYPES,
            frozenset(domain["properties"]["event_type"]["enum"]),
        )


if __name__ == "__main__":
    unittest.main()
