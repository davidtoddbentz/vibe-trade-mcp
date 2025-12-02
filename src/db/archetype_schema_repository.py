"""Repository for archetype schema data access from JSON file.

This layer abstracts data access and returns domain models.
The repository owns the conversion from raw JSON format to domain models.
"""

import json
from pathlib import Path

from src.models.archetype_schema import ArchetypeSchema


class ArchetypeSchemaRepository:
    """Repository for archetype schema read operations.

    Returns domain models (ArchetypeSchema objects) from JSON file.
    The repository owns the conversion from raw JSON format to domain models.
    """

    def __init__(self, schema_file: Path | None = None):
        """Initialize repository.

        Args:
            schema_file: Optional path to schema JSON file. If None, uses default location.
        """
        if schema_file is None:
            # Default to data/archetype_schema.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            schema_file = project_root / "data" / "archetype_schema.json"
        self.schema_file = schema_file
        self._schemas: dict[str, ArchetypeSchema] | None = None

    def _load_schemas(self) -> dict[str, ArchetypeSchema]:
        """Load all schemas from JSON file and cache them.

        Returns:
            Dictionary mapping type_id to ArchetypeSchema domain model
        """
        if self._schemas is not None:
            return self._schemas

        if not self.schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_file}")

        with open(self.schema_file) as f:
            data = json.load(f)

        # Handle both old format (list) and new format (object with "schemas" key)
        if isinstance(data, dict) and "schemas" in data:
            schema_list = data["schemas"]
        elif isinstance(data, list):
            schema_list = data
        else:
            raise ValueError(
                f"Expected list or object with 'schemas' key in {self.schema_file}, got {type(data)}"
            )

        self._schemas = {}
        for schema_data in schema_list:
            schema = ArchetypeSchema.from_dict(schema_data)
            self._schemas[schema.type_id] = schema

        return self._schemas

    def get_by_type_id(self, type_id: str) -> ArchetypeSchema | None:
        """Get schema by archetype type ID.

        Args:
            type_id: The archetype identifier (e.g., 'signal.trend_pullback')

        Returns:
            ArchetypeSchema domain model or None if not found
        """
        schemas = self._load_schemas()
        return schemas.get(type_id)

    def get_all(self) -> list[ArchetypeSchema]:
        """Get all schemas from JSON file.

        Returns:
            List of all ArchetypeSchema domain models
        """
        schemas = self._load_schemas()
        return list(schemas.values())
