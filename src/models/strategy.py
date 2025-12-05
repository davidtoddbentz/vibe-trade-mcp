"""Strategy domain model for trading strategies."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Card attachment within a strategy.

    Represents a card that's been attached to a strategy with a specific role
    and optional slot overrides. Execution order is determined by role:
    gates execute first, then entries, then exits, then overlays.
    """

    card_id: str = Field(..., description="Card identifier")
    role: str = Field(
        ...,
        description="Card role: entry, gate, exit, or overlay",
    )
    enabled: bool = Field(default=True, description="Whether attachment is enabled")
    overrides: dict[str, Any] = Field(
        default_factory=dict, description="Slot value overrides (merged with card slots)"
    )
    follow_latest: bool = Field(
        default=False,
        description="If true, use latest card version; if false, use pinned card_revision_id",
    )
    card_revision_id: str | None = Field(
        None,
        description="Pinned card revision identifier (used when follow_latest=false)",
    )


class Strategy(BaseModel):
    """Trading strategy domain model.

    A strategy is a composition of cards (entries, gates, exits, etc.) with
    universe selection. Risk and execution parameters are configured when
    the strategy is run, not at creation time.
    """

    id: str = Field(..., description="Strategy identifier (Firestore document ID)")
    owner_id: str | None = Field(None, description="Owner identifier (optional for MVP)")
    name: str = Field(..., description="Strategy name")
    status: str = Field(
        default="draft",
        description="Strategy status: draft, ready, running, paused, stopped, or error",
    )
    universe: list[str] = Field(
        default_factory=list, description="Trading universe symbols (e.g., ['BTC-USD'])"
    )
    attachments: list[Attachment] = Field(
        default_factory=list, description="Attached cards with roles and overrides"
    )
    version: int = Field(default=1, description="Strategy version number")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")

    @classmethod
    def from_dict(cls, data: dict[str, Any], strategy_id: str | None = None) -> "Strategy":
        """Create Strategy from dictionary (e.g., from Firestore).

        Args:
            data: Dictionary containing strategy data
            strategy_id: Optional strategy ID (if not in data dict, e.g., from Firestore document ID)
        """
        data_copy = data.copy()
        # If strategy_id is provided separately (from Firestore doc ID), use it
        if strategy_id is not None:
            data_copy["id"] = strategy_id
        # Convert attachments list to Attachment objects
        # Strip out 'order' field if present (legacy field, no longer used)
        if "attachments" in data_copy:
            cleaned_attachments = []
            for att in data_copy["attachments"]:
                att_copy = att.copy()
                att_copy.pop("order", None)  # Remove order field if present
                cleaned_attachments.append(Attachment(**att_copy))
            data_copy["attachments"] = cleaned_attachments
        return cls(**data_copy)

    def to_dict(self) -> dict[str, Any]:
        """Convert Strategy to dictionary for Firestore storage."""
        return {
            "owner_id": self.owner_id,
            "name": self.name,
            "status": self.status,
            "universe": self.universe,
            "attachments": [att.model_dump() for att in self.attachments],
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def now_iso() -> str:
        """Get current timestamp in ISO8601 format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
