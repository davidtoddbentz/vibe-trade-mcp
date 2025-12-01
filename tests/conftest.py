"""Pytest configuration and fixtures."""

import os

import pytest

from src.db.archetype_repository import ArchetypeRepository
from src.db.firestore_client import FirestoreClient


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Automatically set test environment variables for all tests.

    This fixture runs automatically (autouse=True) and sets default
    test environment variables if they're not already set. Tests can
    override these by setting env vars before this fixture runs, or
    by using monkeypatch in their own fixtures.
    """
    # Set default test values only if not already set
    # This allows tests to override by setting env vars explicitly
    if "GOOGLE_CLOUD_PROJECT" not in os.environ:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    if "FIRESTORE_DATABASE" not in os.environ:
        monkeypatch.setenv("FIRESTORE_DATABASE", "(default)")


@pytest.fixture
def firestore_client():
    """Create a Firestore client for testing.

    Automatically uses emulator if FIRESTORE_EMULATOR_HOST is set,
    otherwise connects to production. Just like a database URL.
    """
    # Reset singleton before test
    FirestoreClient.reset_client()

    # Read project from environment
    # These are now guaranteed to be set by setup_test_env fixture
    project = os.getenv("GOOGLE_CLOUD_PROJECT")

    # Create client - environment variables control behavior automatically
    # If FIRESTORE_EMULATOR_HOST is set, it uses emulator
    # If not, it connects to production (or fails if not configured)
    client = FirestoreClient.get_client(project=project)

    yield client

    # Cleanup: reset singleton after test
    FirestoreClient.reset_client()


@pytest.fixture
def archetype_repository(firestore_client):
    """Create an ArchetypeRepository for testing."""
    return ArchetypeRepository(client=firestore_client)


@pytest.fixture
def sample_archetype_data():
    """Sample archetype data for testing."""
    return {
        "id": "signal.test_archetype",
        "version": 1,
        "title": "Test Archetype",
        "summary": "A test archetype for unit tests",
        "kind": "signal",
        "tags": ["test"],
        "required_slots": ["tf", "symbol"],
        "schema_etag": 'W/"test.v1"',
        "deprecated": False,
        "hints": {"preferred_tfs": ["1h"]},
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_archetype(archetype_repository, sample_archetype_data):
    """Create a sample archetype in the test database."""
    arch_id = sample_archetype_data.pop("id")
    archetype_repository.create_or_update(arch_id, sample_archetype_data)
    yield arch_id
    # Cleanup: delete the test archetype
    archetype_repository.collection.document(arch_id).delete()
