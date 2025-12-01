"""Card domain model for trading strategy cards."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Card(BaseModel):
    """Trading strategy card domain model.

    A card represents a concrete instance of an archetype with filled slots.
    Cards are stored in Firestore and can be linked to strategies.
    """

    id: str = Field(..., description="Card identifier (Firestore document ID)")
    type: str = Field(..., description="Archetype identifier (e.g., 'signal.trend_pullback')")
    slots: dict[str, Any] = Field(..., description="Slot values validated against archetype schema")
    schema_etag: str = Field(
        ..., description="ETag of the schema used for validation (for version tracking)"
    )
    created_at: str = Field(..., description="ISO8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")

    @classmethod
    def from_dict(cls, data: dict[str, Any], card_id: str | None = None) -> "Card":
        """Create Card from dictionary (e.g., from Firestore).

        Args:
            data: Dictionary containing card data
            card_id: Optional card ID (if not in data dict, e.g., from Firestore document ID)
        """
        data_copy = data.copy()
        # If card_id is provided separately (from Firestore doc ID), use it
        if card_id is not None:
            data_copy["id"] = card_id
        return cls(**data_copy)

    def to_dict(self) -> dict[str, Any]:
        """Convert Card to dictionary for Firestore storage."""
        return {
            "type": self.type,
            "slots": self.slots,
            "schema_etag": self.schema_etag,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def now_iso() -> str:
        """Get current timestamp in ISO8601 format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
