"""Pydantic models for archetype domain objects."""

from typing import Any

from pydantic import BaseModel, Field


class ArchetypeHints(BaseModel):
    """Hints for archetype usage."""

    preferred_tfs: list[str] = Field(default_factory=list, description="Preferred timeframes")


class Archetype(BaseModel):
    """Trading strategy archetype domain model."""

    id: str = Field(..., description="Archetype identifier (e.g., 'signal.trend_pullback')")
    version: int = Field(..., description="Archetype version number")
    title: str = Field(..., description="Human-readable title")
    summary: str = Field(..., description="Brief description of the archetype")
    kind: str = Field(..., description="Archetype kind (e.g., 'signal', 'gate')")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    required_slots: list[str] = Field(..., description="List of required slot names")
    schema_etag: str = Field(..., description="Weak ETag for schema caching")
    deprecated: bool = Field(default=False, description="Whether this archetype is deprecated")
    hints: ArchetypeHints = Field(default_factory=ArchetypeHints, description="Usage hints")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Archetype":
        """Create Archetype from dictionary (e.g., from Firestore)."""
        # Create a copy to avoid mutating the original
        data_copy = data.copy()
        # Handle nested hints dict
        hints_data = data_copy.pop("hints", {})
        hints = ArchetypeHints(**hints_data) if hints_data else ArchetypeHints()

        return cls(hints=hints, **data_copy)
