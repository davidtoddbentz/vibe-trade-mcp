"""Firestore client and connection management."""

from google.cloud import firestore
from google.cloud.firestore import Client


class FirestoreClient:
    """Firestore client for both local (emulator) and production.

    Automatically uses emulator if FIRESTORE_EMULATOR_HOST is set,
    otherwise connects to production Firestore.
    No code changes needed - environment variable controls behavior.
    """

    _client: Client | None = None
    _project: str | None = None
    _database: str | None = None

    @classmethod
    def get_client(cls, project: str, database: str | None = None) -> Client:
        """Get or create Firestore client.

        Args:
            project: GCP project ID (required).
            database: Database name. Use None for "(default)" database (emulator limitation).

        The Firestore client library automatically detects FIRESTORE_EMULATOR_HOST
        and routes to emulator if set. Otherwise connects to production.
        """
        if cls._client is None:
            cls._project = project
            cls._database = database
            # Client automatically uses emulator if FIRESTORE_EMULATOR_HOST is set
            # No conditional logic needed - environment variable controls it
            cls._client = firestore.Client(project=project, database=database)
        return cls._client

    @classmethod
    def reset_client(cls) -> None:
        """Reset client (useful for testing)."""
        cls._client = None
        cls._project = None
