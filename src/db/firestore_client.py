"""Firestore client and connection management."""

import os

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

    @classmethod
    def get_client(cls, project: str | None = None) -> Client:
        """Get or create Firestore client.

        Args:
            project: GCP project ID. If None and client not yet created, raises ValueError.

        The Firestore client library automatically detects FIRESTORE_EMULATOR_HOST
        and routes to emulator if set. Otherwise connects to production.
        """
        if cls._client is None:
            if project is None:
                raise ValueError(
                    "project parameter must be provided. "
                    "Read GOOGLE_CLOUD_PROJECT from environment in main.py/conftest.py"
                )
            cls._project = project
            # Database name must be explicitly set via environment variable
            database = os.getenv("FIRESTORE_DATABASE")
            if not database:
                raise ValueError(
                    "FIRESTORE_DATABASE environment variable must be set. "
                    "For emulator: FIRESTORE_DATABASE=(default) "
                    "For production: FIRESTORE_DATABASE=strategy"
                )
            # Use None for "(default)" database (emulator limitation)
            database = None if database == "(default)" else database
            # Client automatically uses emulator if FIRESTORE_EMULATOR_HOST is set
            # No conditional logic needed - environment variable controls it
            cls._client = firestore.Client(project=project, database=database)
        return cls._client

    @classmethod
    def reset_client(cls) -> None:
        """Reset client (useful for testing)."""
        cls._client = None
        cls._project = None
