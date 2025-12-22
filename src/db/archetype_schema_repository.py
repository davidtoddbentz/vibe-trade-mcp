"""Repository for archetype schema data access from JSON file.

This layer abstracts data access and returns domain models.
The repository owns the conversion from raw JSON format to domain models.
"""

import json
from pathlib import Path

from ..models.archetype_schema import ArchetypeSchema


class ArchetypeSchemaRepository:
    """Repository for archetype schema read operations.

    Returns domain models (ArchetypeSchema objects) from JSON file.
    The repository owns the conversion from raw JSON format to domain models.
    """

    def __init__(
        self,
        schema_file: Path | None = None,
        exit_schema_file: Path | None = None,
        gate_schema_file: Path | None = None,
        overlay_schema_file: Path | None = None,
    ):
        """Initialize repository.

        Args:
            schema_file: Optional path to entry schema JSON file. If None, uses default location.
            exit_schema_file: Optional path to exit schema JSON file. If None, uses default location.
            gate_schema_file: Optional path to gate schema JSON file. If None, uses default location.
            overlay_schema_file: Optional path to overlay schema JSON file. If None, uses default location.
        """
        project_root = Path(__file__).parent.parent.parent
        if schema_file is None:
            schema_file = project_root / "data" / "archetype_schema.json"
        if exit_schema_file is None:
            exit_schema_file = project_root / "data" / "exit_archetype_schema.json"
        if gate_schema_file is None:
            gate_schema_file = project_root / "data" / "gate_archetype_schema.json"
        if overlay_schema_file is None:
            overlay_schema_file = project_root / "data" / "overlay_archetype_schema.json"
        self.schema_file = schema_file
        self.exit_schema_file = exit_schema_file
        self.gate_schema_file = gate_schema_file
        self.overlay_schema_file = overlay_schema_file
        self._schemas: dict[str, ArchetypeSchema] | None = None

    def _load_schemas(self) -> dict[str, ArchetypeSchema]:
        """Load all schemas from JSON files and cache them.

        Merges entry schemas from archetype_schema.json, exit schemas from exit_archetype_schema.json,
        gate schemas from gate_archetype_schema.json, and overlay schemas from overlay_archetype_schema.json.

        Returns:
            Dictionary mapping type_id to ArchetypeSchema domain model
        """
        if self._schemas is not None:
            return self._schemas

        self._schemas = {}

        # Load entry schemas
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

        for schema_data in schema_list:
            schema = ArchetypeSchema.from_dict(schema_data)
            self._schemas[schema.type_id] = schema

        # Load exit schemas (if file exists)
        if self.exit_schema_file.exists():
            with open(self.exit_schema_file) as f:
                exit_data = json.load(f)

            if isinstance(exit_data, dict) and "schemas" in exit_data:
                exit_schema_list = exit_data["schemas"]
            elif isinstance(exit_data, list):
                exit_schema_list = exit_data
            else:
                raise ValueError(
                    f"Expected list or object with 'schemas' key in {self.exit_schema_file}, got {type(exit_data)}"
                )

            for schema_data in exit_schema_list:
                schema = ArchetypeSchema.from_dict(schema_data)
                self._schemas[schema.type_id] = schema

        # Load gate schemas (if file exists)
        if self.gate_schema_file.exists():
            with open(self.gate_schema_file) as f:
                gate_data = json.load(f)

            if isinstance(gate_data, dict) and "schemas" in gate_data:
                gate_schema_list = gate_data["schemas"]
            elif isinstance(gate_data, list):
                gate_schema_list = gate_data
            else:
                raise ValueError(
                    f"Expected list or object with 'schemas' key in {self.gate_schema_file}, got {type(gate_data)}"
                )

            for schema_data in gate_schema_list:
                schema = ArchetypeSchema.from_dict(schema_data)
                self._schemas[schema.type_id] = schema

        # Load overlay schemas (if file exists)
        if self.overlay_schema_file.exists():
            with open(self.overlay_schema_file) as f:
                overlay_data = json.load(f)

            if isinstance(overlay_data, dict) and "schemas" in overlay_data:
                overlay_schema_list = overlay_data["schemas"]
            elif isinstance(overlay_data, list):
                overlay_schema_list = overlay_data
            else:
                raise ValueError(
                    f"Expected list or object with 'schemas' key in {self.overlay_schema_file}, got {type(overlay_data)}"
                )

            for schema_data in overlay_schema_list:
                schema = ArchetypeSchema.from_dict(schema_data)
                self._schemas[schema.type_id] = schema

        return self._schemas

    def get_by_type_id(self, type_id: str) -> ArchetypeSchema | None:
        """Get schema by archetype type ID.

        Args:
                type_id: The archetype identifier (e.g., 'entry.trend_pullback')

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
