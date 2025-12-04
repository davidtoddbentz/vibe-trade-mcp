"""Pydantic models for archetype schema domain objects."""

from typing import Any

from pydantic import BaseModel, Field


class SchemaConstraints(BaseModel):
    """Constraints for archetype schema."""

    min_history_bars: int | None = Field(None, description="Minimum history bars required")
    pit_safe: bool | None = Field(None, description="Point-in-time safe")
    warmup_hint: str | None = Field(None, description="Warmup hint message")


class SchemaExample(BaseModel):
    """Example for archetype schema."""

    human: str = Field(..., description="Human-readable description")
    slots: dict[str, Any] = Field(..., description="Example slot values")


class ArchetypeSchema(BaseModel):
    """Archetype schema domain model with full JSON Schema and metadata."""

    type_id: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')")
    schema_version: int = Field(..., description="Schema version number")
    etag: str = Field(
        ...,
        description="Weak ETag for schema caching (e.g., 'W/\"seed-v1.entry.trend_pullback\"')",
    )
    json_schema: dict[str, Any] = Field(..., description="JSON Schema object for validation")
    constraints: SchemaConstraints = Field(
        default_factory=SchemaConstraints, description="Schema constraints"
    )
    slot_hints: dict[str, Any] = Field(default_factory=dict, description="Hints for slot values")
    examples: list[SchemaExample] = Field(
        default_factory=list, description="Example slot configurations"
    )
    notes: list[str] = Field(default_factory=list, description="Additional notes")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchetypeSchema":
        """Create ArchetypeSchema from dictionary (e.g., from JSON file)."""
        data_copy = data.copy()

        # Handle nested constraints dict
        constraints_data = data_copy.pop("constraints", {})
        constraints = (
            SchemaConstraints(**constraints_data) if constraints_data else SchemaConstraints()
        )

        # Handle nested examples list
        examples_data = data_copy.pop("examples", [])
        examples = [SchemaExample(**ex) for ex in examples_data] if examples_data else []

        return cls(constraints=constraints, examples=examples, **data_copy)
