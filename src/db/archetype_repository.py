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

    def __init__(
        self,
        archetypes_file: Path | None = None,
        exit_archetypes_file: Path | None = None,
        gate_archetypes_file: Path | None = None,
        overlay_archetypes_file: Path | None = None,
    ):
        """Initialize repository.

        Args:
            archetypes_file: Optional path to entry archetypes JSON file. If None, uses default location.
            exit_archetypes_file: Optional path to exit archetypes JSON file. If None, uses default location.
            gate_archetypes_file: Optional path to gate archetypes JSON file. If None, uses default location.
            overlay_archetypes_file: Optional path to overlay archetypes JSON file. If None, uses default location.
        """
        project_root = Path(__file__).parent.parent.parent
        if archetypes_file is None:
            archetypes_file = project_root / "data" / "archetypes.json"
        if exit_archetypes_file is None:
            exit_archetypes_file = project_root / "data" / "exit_archetypes.json"
        if gate_archetypes_file is None:
            gate_archetypes_file = project_root / "data" / "gate_archetypes.json"
        if overlay_archetypes_file is None:
            overlay_archetypes_file = project_root / "data" / "overlay_archetypes.json"
        self.archetypes_file = archetypes_file
        self.exit_archetypes_file = exit_archetypes_file
        self.gate_archetypes_file = gate_archetypes_file
        self.overlay_archetypes_file = overlay_archetypes_file
        self._archetypes: dict[str, Archetype] | None = None

    def _load_archetypes(self) -> dict[str, Archetype]:
        """Load all archetypes from JSON files and cache them.

        Merges entry archetypes from archetypes.json, exit archetypes from exit_archetypes.json,
        gate archetypes from gate_archetypes.json, and overlay archetypes from overlay_archetypes.json.

        Returns:
            Dictionary mapping archetype ID to Archetype domain model
        """
        if self._archetypes is not None:
            return self._archetypes

        self._archetypes = {}

        # Load entry archetypes
        if not self.archetypes_file.exists():
            raise FileNotFoundError(f"Archetypes file not found: {self.archetypes_file}")

        with open(self.archetypes_file) as f:
            data = json.load(f)

        # Handle both old format (list) and new format (object with "archetypes" key)
        if isinstance(data, list):
            archetype_list = data
        elif isinstance(data, dict) and "archetypes" in data:
            archetype_list = data["archetypes"]
        else:
            raise ValueError(
                f"Expected list or object with 'archetypes' key in {self.archetypes_file}, got {type(data)}"
            )

        for arch_data in archetype_list:
            archetype = Archetype.from_dict(arch_data)
            self._archetypes[archetype.id] = archetype

        # Load exit archetypes (if file exists)
        if self.exit_archetypes_file.exists():
            with open(self.exit_archetypes_file) as f:
                exit_data = json.load(f)

            if isinstance(exit_data, list):
                exit_archetype_list = exit_data
            elif isinstance(exit_data, dict) and "archetypes" in exit_data:
                exit_archetype_list = exit_data["archetypes"]
            else:
                raise ValueError(
                    f"Expected list or object with 'archetypes' key in {self.exit_archetypes_file}, got {type(exit_data)}"
                )

            for arch_data in exit_archetype_list:
                archetype = Archetype.from_dict(arch_data)
                self._archetypes[archetype.id] = archetype

        # Load gate archetypes (if file exists)
        if self.gate_archetypes_file.exists():
            with open(self.gate_archetypes_file) as f:
                gate_data = json.load(f)

            if isinstance(gate_data, list):
                gate_archetype_list = gate_data
            elif isinstance(gate_data, dict) and "archetypes" in gate_data:
                gate_archetype_list = gate_data["archetypes"]
            else:
                raise ValueError(
                    f"Expected list or object with 'archetypes' key in {self.gate_archetypes_file}, got {type(gate_data)}"
                )

            for arch_data in gate_archetype_list:
                archetype = Archetype.from_dict(arch_data)
                self._archetypes[archetype.id] = archetype

        # Load overlay archetypes (if file exists)
        if self.overlay_archetypes_file.exists():
            with open(self.overlay_archetypes_file) as f:
                overlay_data = json.load(f)

            if isinstance(overlay_data, list):
                overlay_archetype_list = overlay_data
            elif isinstance(overlay_data, dict) and "archetypes" in overlay_data:
                overlay_archetype_list = overlay_data["archetypes"]
            else:
                raise ValueError(
                    f"Expected list or object with 'archetypes' key in {self.overlay_archetypes_file}, got {type(overlay_data)}"
                )

            for arch_data in overlay_archetype_list:
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
