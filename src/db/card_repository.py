"""Repository for card data access from Firestore.

This layer abstracts data access and returns domain models.
The repository owns the conversion from Firestore documents to domain models.
"""

from google.cloud.firestore import Client

from src.models.card import Card


class CardRepository:
    """Repository for card CRUD operations.

    Returns domain models (Card objects) from Firestore.
    The repository owns the conversion from Firestore documents to domain models.
    """

    def __init__(self, client: Client):
        """Initialize repository.

        Args:
            client: Firestore client (required).
        """
        self.client = client
        self.collection = "cards"

    def create(self, card: Card) -> Card:
        """Create a new card in Firestore.

        Args:
            card: Card to create. The id field will be ignored - Firestore will generate it.

        Returns:
            Card with generated ID and timestamps
        """
        # Generate timestamps
        now = Card.now_iso()
        card.created_at = now
        card.updated_at = now

        # Convert to dict (excluding id - Firestore will generate it)
        card_dict = card.to_dict()

        # Add to Firestore (auto-generates document ID)
        doc_ref = self.client.collection(self.collection).add(card_dict)[1]

        # Return card with generated ID
        return Card(
            id=doc_ref.id,
            type=card.type,
            slots=card.slots,
            schema_etag=card.schema_etag,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )

    def get_by_id(self, card_id: str) -> Card | None:
        """Get a card by ID.

        Args:
            card_id: Card identifier

        Returns:
            Card if found, None otherwise
        """
        doc_ref = self.client.collection(self.collection).document(card_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Card.from_dict(data, card_id=doc.id)

    def get_all(self) -> list[Card]:
        """Get all cards.

        Returns:
            List of all cards
        """
        docs = self.client.collection(self.collection).stream()
        cards = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                cards.append(Card.from_dict(data, card_id=doc.id))
        return cards

    def update(self, card: Card) -> Card:
        """Update an existing card.

        Args:
            card: Card to update (must have valid id)

        Returns:
            Updated card with new updated_at timestamp

        Raises:
            ValueError: If card.id is not set or card doesn't exist
        """
        if not card.id:
            raise ValueError("Card ID is required for update")

        # Check if card exists
        existing = self.get_by_id(card.id)
        if existing is None:
            raise ValueError(f"Card not found: {card.id}")

        # Update timestamp
        card.updated_at = Card.now_iso()

        # Update in Firestore
        doc_ref = self.client.collection(self.collection).document(card.id)
        doc_ref.update(card.to_dict())

        return card

    def delete(self, card_id: str) -> None:
        """Delete a card by ID.

        Args:
            card_id: Card identifier

        Raises:
            ValueError: If card doesn't exist
        """
        doc_ref = self.client.collection(self.collection).document(card_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise ValueError(f"Card not found: {card_id}")

        doc_ref.delete()
