"""Repository for archetype data access from JSON file.

This layer abstracts data access and returns domain models.
The repository owns the conversion from raw JSON format to domain models.
"""

import json
from pathlib import Path

from src.models.archetype import Archetype


class ArchetypeRepository:
    """Repository for archetype read operations.

    Returns domain models (Archetype objects) from JSON file.
    The repository owns the conversion from raw JSON format to domain models.
    """

    def __init__(self, archetypes_file: Path | None = None):
        """Initialize repository.

        Args:
            archetypes_file: Optional path to archetypes JSON file. If None, uses default location.
        """
        if archetypes_file is None:
            # Default to data/archetypes.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            archetypes_file = project_root / "data" / "archetypes.json"
        self.archetypes_file = archetypes_file
        self._archetypes: dict[str, Archetype] | None = None

    def _load_archetypes(self) -> dict[str, Archetype]:
        """Load all archetypes from JSON file and cache them.

        Returns:
            Dictionary mapping archetype ID to Archetype domain model
        """
        if self._archetypes is not None:
            return self._archetypes

        if not self.archetypes_file.exists():
            raise FileNotFoundError(f"Archetypes file not found: {self.archetypes_file}")

        with open(self.archetypes_file) as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"Expected list in {self.archetypes_file}, got {type(data)}")

        self._archetypes = {}
        for arch_data in data:
            archetype = Archetype.from_dict(arch_data)
            self._archetypes[archetype.id] = archetype

        return self._archetypes

    def get_all(self) -> list[Archetype]:
        """Get all archetypes from JSON file.

        Returns:
            List of all Archetype domain models
        """
        archetypes = self._load_archetypes()
        return list(archetypes.values())

    def get_by_id(self, archetype_id: str) -> Archetype | None:
        """Get archetype by ID.

        Args:
            archetype_id: The archetype identifier

        Returns:
            Archetype domain model or None if not found
        """
        archetypes = self._load_archetypes()
        return archetypes.get(archetype_id)

    def get_non_deprecated(self) -> list[Archetype]:
        """Get all non-deprecated archetypes.

        Returns:
            List of non-deprecated Archetype domain models
        """
        archetypes = self._load_archetypes()
        return [arch for arch in archetypes.values() if not arch.deprecated]
