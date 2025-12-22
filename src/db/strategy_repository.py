"""Repository for strategy data access from Firestore.

This layer abstracts data access and returns domain models.
The repository owns the conversion from Firestore documents to domain models.
"""

from google.cloud.firestore import Client

from ..models.strategy import Strategy


class StrategyRepository:
    """Repository for strategy CRUD operations.

    Returns domain models (Strategy objects) from Firestore.
    The repository owns the conversion from Firestore documents to domain models.
    """

    def __init__(self, client: Client):
        """Initialize repository.

        Args:
            client: Firestore client (required).
        """
        self.client = client
        self.collection = "strategies"

    def create(self, strategy: Strategy) -> Strategy:
        """Create a new strategy in Firestore.

        Args:
            strategy: Strategy to create. The id field will be ignored - Firestore will generate it.

        Returns:
            Strategy with generated ID and timestamps
        """
        # Generate timestamps
        now = Strategy.now_iso()
        strategy.created_at = now
        strategy.updated_at = now

        # Convert to dict (excluding id - Firestore will generate it)
        strategy_dict = strategy.to_dict()

        # Add to Firestore (auto-generates document ID)
        doc_ref = self.client.collection(self.collection).add(strategy_dict)[1]

        # Return strategy with generated ID
        return Strategy.from_dict(strategy_dict, strategy_id=doc_ref.id)

    def get_by_id(self, strategy_id: str) -> Strategy | None:
        """Get a strategy by ID.

        Args:
            strategy_id: Strategy identifier

        Returns:
            Strategy if found, None otherwise
        """
        doc_ref = self.client.collection(self.collection).document(strategy_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Strategy.from_dict(data, strategy_id=doc.id)

    def get_all(self) -> list[Strategy]:
        """Get all strategies.

        Returns:
            List of all strategies
        """
        docs = self.client.collection(self.collection).stream()
        strategies = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                strategies.append(Strategy.from_dict(data, strategy_id=doc.id))
        return strategies

    def update(self, strategy: Strategy) -> Strategy:
        """Update an existing strategy.

        Args:
            strategy: Strategy to update (must have valid id)

        Returns:
            Updated strategy with new updated_at timestamp and incremented version

        Raises:
            ValueError: If strategy.id is not set or strategy doesn't exist
        """
        if not strategy.id:
            raise ValueError("Strategy ID is required for update")

        # Check if strategy exists
        existing = self.get_by_id(strategy.id)
        if existing is None:
            raise ValueError(f"Strategy not found: {strategy.id}")

        # Update timestamp and increment version
        strategy.updated_at = Strategy.now_iso()
        strategy.version = existing.version + 1

        # Update in Firestore
        doc_ref = self.client.collection(self.collection).document(strategy.id)
        doc_ref.update(strategy.to_dict())

        return strategy

    def delete(self, strategy_id: str) -> None:
        """Delete a strategy by ID.

        Args:
            strategy_id: Strategy identifier

        Raises:
            ValueError: If strategy doesn't exist
        """
        doc_ref = self.client.collection(self.collection).document(strategy_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise ValueError(f"Strategy not found: {strategy_id}")

        doc_ref.delete()
