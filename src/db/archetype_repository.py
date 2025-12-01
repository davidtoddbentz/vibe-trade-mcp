"""Repository for archetype data access using Firestore.

This layer abstracts Firestore operations and returns raw dictionaries.
Domain models are created in the service/tool layer.
"""

from typing import Any

from google.cloud.firestore import Client
from google.cloud.firestore_v1 import FieldFilter

from src.db.firestore_client import FirestoreClient


class ArchetypeRepository:
    """Repository for archetype CRUD operations.

    Returns raw dictionaries (DB-like interface) from Firestore.
    Domain models are created in the service/tool layer.
    """

    def __init__(self, client: Client | None = None):
        """Initialize repository.

        Args:
            client: Optional Firestore client. If None, uses singleton client.
        """
        self.client = client or FirestoreClient.get_client()
        self.collection = self.client.collection("archetypes")

    def get_all(self) -> list[dict[str, Any]]:
        """Get all archetypes from Firestore.

        Returns:
            List of archetype dictionaries (raw data from Firestore)
        """
        docs = self.collection.stream()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]

    def get_by_id(self, archetype_id: str) -> dict[str, Any] | None:
        """Get archetype by ID.

        Args:
            archetype_id: The archetype identifier (document ID in Firestore)

        Returns:
            Archetype dictionary or None if not found
        """
        doc = self.collection.document(archetype_id).get()
        if not doc.exists:
            return None
        return doc.to_dict() | {"id": doc.id}

    def get_non_deprecated(self) -> list[dict[str, Any]]:
        """Get all non-deprecated archetypes.

        Returns:
            List of non-deprecated archetype dictionaries
        """
        docs = self.collection.where(filter=FieldFilter("deprecated", "==", False)).stream()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]

    def create_or_update(self, archetype_id: str, data: dict[str, Any]) -> None:
        """Create or update an archetype.

        Args:
            archetype_id: The archetype identifier (document ID)
            data: Archetype data dictionary (without 'id' field)
        """
        # Remove 'id' from data if present (it's the document ID, not a field)
        data_clean = {k: v for k, v in data.items() if k != "id"}
        # Use merge=True to update existing documents or create new ones
        self.collection.document(archetype_id).set(data_clean, merge=True)
