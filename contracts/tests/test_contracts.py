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

        self.assertEqual(len(protos), 7)
        for proto in protos:
            source = proto.read_text()
            self.assertIn('syntax = "proto3";', source)
            self.assertIn(".v1;", source)

    def test_event_schemas_are_valid_json_schema_documents(self) -> None:
        schemas = sorted((CONTRACTS / "events").glob("*.json"))

        self.assertEqual(len(schemas), 5)
        for path in schemas:
            schema = json.loads(path.read_text())
            self.assertEqual(schema["type"], "object")
            self.assertTrue(schema["required"])
            self.assertIn("timestamp", schema["properties"])

    def test_constants_are_unique(self) -> None:
        self.assertEqual(ROLES, {"owner", "coordinator", "viewer"})
        self.assertEqual(PERMISSIONS, {"view", "submit", "approve", "manage", "delete"})
        self.assertEqual(len(EVENT_TYPES), 10)


if __name__ == "__main__":
    unittest.main()
