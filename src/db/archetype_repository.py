"""Repository for archetype data access using Firestore.

This layer abstracts Firestore operations and returns domain models.
The repository owns the conversion from raw database format to domain models.
"""

from google.cloud.firestore import Client
from google.cloud.firestore_v1 import FieldFilter

from src.db.firestore_client import FirestoreClient
from src.models.archetype import Archetype


class ArchetypeRepository:
    """Repository for archetype CRUD operations.

    Returns domain models (Archetype objects) from Firestore.
    The repository owns the conversion from raw database format to domain models.
    """

    def __init__(self, client: Client | None = None):
        """Initialize repository.

        Args:
            client: Optional Firestore client. If None, uses singleton client.
        """
        self.client = client or FirestoreClient.get_client()
        self.collection = self.client.collection("archetypes")

    def _to_domain_model(self, doc_id: str, data: dict) -> Archetype:
        """Convert raw Firestore document to domain model.

        Args:
            doc_id: Document ID from Firestore
            data: Raw document data from Firestore

        Returns:
            Archetype domain model
        """
        return Archetype.from_dict(data | {"id": doc_id})

    def get_all(self) -> list[Archetype]:
        """Get all archetypes from Firestore.

        Returns:
            List of Archetype domain models
        """
        docs = self.collection.stream()
        return [self._to_domain_model(doc.id, doc.to_dict()) for doc in docs]

    def get_by_id(self, archetype_id: str) -> Archetype | None:
        """Get archetype by ID.

        Args:
            archetype_id: The archetype identifier (document ID in Firestore)

        Returns:
            Archetype domain model or None if not found
        """
        doc = self.collection.document(archetype_id).get()
        if not doc.exists:
            return None
        return self._to_domain_model(doc.id, doc.to_dict())

    def get_non_deprecated(self) -> list[Archetype]:
        """Get all non-deprecated archetypes.

        Returns:
            List of non-deprecated Archetype domain models
        """
        docs = self.collection.where(filter=FieldFilter("deprecated", "==", False)).stream()
        return [self._to_domain_model(doc.id, doc.to_dict()) for doc in docs]

    def create_or_update(self, archetype_id: str, data: dict) -> None:
        """Create or update an archetype.

        Args:
            archetype_id: The archetype identifier (document ID)
            data: Archetype data dictionary (without 'id' field)
        """
        # Remove 'id' from data if present (it's the document ID, not a field)
        data_clean = {k: v for k, v in data.items() if k != "id"}
        # Use merge=True to update existing documents or create new ones
        self.collection.document(archetype_id).set(data_clean, merge=True)

    def delete(self, archetype_id: str) -> None:
        """Delete an archetype by ID.

        Args:
            archetype_id: The archetype identifier (document ID)
        """
        self.collection.document(archetype_id).delete()

    def delete_all(self) -> None:
        """Delete all archetypes. Useful for test cleanup."""
        docs = self.collection.stream()
        for doc in docs:
            doc.reference.delete()
