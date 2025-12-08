#!/usr/bin/env python3
"""Test script to verify MCP resources are working."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.db.archetype_repository import ArchetypeRepository
from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.tools.resource_tools import _get_archetypes_json, _get_schemas_json


def test_archetype_resources():
    """Test archetype resource generation."""
    print("🧪 Testing archetype resources...")

    repo = ArchetypeRepository()

    for kind in ["entry", "exit", "gate", "overlay", "all"]:
        print(f"\n  Testing archetypes://{kind}...")
        try:
            json_data = _get_archetypes_json(repo, kind)
            data = json.loads(json_data)

            assert "archetypes" in data, f"Missing 'archetypes' key for {kind}"
            archetypes = data["archetypes"]

            if kind == "all":
                print(f"    ✅ Found {len(archetypes)} total archetypes")
            else:
                print(f"    ✅ Found {len(archetypes)} {kind} archetypes")
                # Verify all are of the correct kind
                for arch in archetypes:
                    assert arch["kind"] == kind, f"Archetype {arch['id']} has wrong kind"

            # Verify structure
            if archetypes:
                first = archetypes[0]
                required_fields = [
                    "id",
                    "version",
                    "title",
                    "summary",
                    "kind",
                    "tags",
                    "required_slots",
                ]
                for field in required_fields:
                    assert field in first, f"Missing required field: {field}"

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    return True


def test_schema_resources():
    """Test schema resource generation."""
    print("\n🧪 Testing schema resources...")

    repo = ArchetypeSchemaRepository()

    for kind in ["entry", "exit", "gate", "overlay", "all"]:
        print(f"\n  Testing archetype-schemas://{kind}...")
        try:
            json_data = _get_schemas_json(repo, kind)
            data = json.loads(json_data)

            assert "schemas" in data, f"Missing 'schemas' key for {kind}"
            schemas = data["schemas"]

            if kind == "all":
                print(f"    ✅ Found {len(schemas)} total schemas")
            else:
                print(f"    ✅ Found {len(schemas)} {kind} schemas")
                # Verify all are of the correct kind
                for schema in schemas:
                    schema_kind = schema["type_id"].split(".", 1)[0]
                    assert schema_kind == kind, f"Schema {schema['type_id']} has wrong kind"
                    assert schema["kind"] == kind, f"Schema {schema['type_id']} missing kind field"

            # Verify structure
            if schemas:
                first = schemas[0]
                required_fields = ["type_id", "schema_version", "etag", "json_schema", "kind"]
                for field in required_fields:
                    assert field in first, f"Missing required field: {field}"

        except Exception as e:
            print(f"    ❌ Error: {e}")
            import traceback

            traceback.print_exc()
            return False

    return True


def main():
    """Run all tests."""
    print("🚀 Testing MCP Resources\n")
    print("=" * 60)

    success = True

    # Test archetype resources
    if not test_archetype_resources():
        success = False

    # Test schema resources
    if not test_schema_resources():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✅ All resource tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())


