#!/usr/bin/env python3
"""Seed archetypes into Firestore.

Works with:
- Local emulator (set FIRESTORE_EMULATOR_HOST)
- Production (set GOOGLE_CLOUD_PROJECT)

Usage:
    # Local (with emulator running)
    export FIRESTORE_EMULATOR_HOST=localhost:8081
    export GOOGLE_CLOUD_PROJECT=demo-project
    uv run python -m src.scripts.seed_archetypes

    # Production
    export GOOGLE_CLOUD_PROJECT=vibe-trade-475704
    uv run python -m src.scripts.seed_archetypes

    # Dry run (see what would be done)
    uv run python -m src.scripts.seed_archetypes --dry-run
"""

import argparse
import json
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.cloud import firestore

# Load .env file if it exists (for local development)
# Preserve explicitly set environment variables before loading .env
env_path = Path(__file__).parent.parent.parent / ".env"
explicit_project = os.getenv("GOOGLE_CLOUD_PROJECT")
explicit_database = os.getenv("FIRESTORE_DATABASE")
explicit_emulator = os.getenv("FIRESTORE_EMULATOR_HOST")

if env_path.exists():
    load_dotenv(env_path, override=True)
    # Restore explicitly set environment variables (they take precedence)
    if explicit_project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = explicit_project
    if explicit_database:
        os.environ["FIRESTORE_DATABASE"] = explicit_database
    # If FIRESTORE_EMULATOR_HOST was explicitly unset (empty string), keep it unset
    if explicit_emulator == "":
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
    elif explicit_emulator is not None:
        os.environ["FIRESTORE_EMULATOR_HOST"] = explicit_emulator


def load_archetypes_from_json() -> list[dict[str, Any]]:
    """Load archetypes from JSON file."""
    project_root = Path(__file__).parent.parent.parent
    json_file = project_root / "data" / "archetypes.json"

    if not json_file.exists():
        raise FileNotFoundError(f"Archetypes JSON file not found: {json_file}")

    with open(json_file) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected list in {json_file}, got {type(data)}")

    return data


def seed_archetypes(dry_run: bool = False) -> tuple[int, int]:
    """Seed archetypes into Firestore.

    Args:
        dry_run: If True, don't actually write to database

    Returns:
        Tuple of (created_count, updated_count)
    """
    # Get project from environment
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("❌ Error: GOOGLE_CLOUD_PROJECT not set", file=sys.stderr)
        sys.exit(1)

    # Check if emulator is running (if using emulator)
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
    if emulator_host and not dry_run:
        host, port = emulator_host.split(":")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            if result != 0:
                print(
                    f"❌ Error: Firestore emulator is not running on {emulator_host}",
                    file=sys.stderr,
                )
                print("   Start it with: make emulator (in another terminal)", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"❌ Error checking emulator connection: {e}", file=sys.stderr)
            sys.exit(1)

    # Load data
    archetypes = load_archetypes_from_json()

    if dry_run:
        print("🌱 [DRY RUN] Would seed archetypes into Firestore...", file=sys.stderr)
        if emulator_host:
            print(f"   Environment: Local Emulator ({emulator_host})", file=sys.stderr)
        else:
            print(f"   Environment: Production ({project})", file=sys.stderr)
        for arch in archetypes:
            arch_id = arch.get("id", "unknown")
            print(
                f"   [DRY RUN] Would create/update: {arch_id} ({arch.get('title')})",
                file=sys.stderr,
            )
        print(f"✅ [DRY RUN] Would seed {len(archetypes)} archetypes", file=sys.stderr)
        return len(archetypes), 0

    # Initialize Firestore client
    print("🌱 Seeding archetypes into Firestore...", file=sys.stderr)
    # Check emulator_host again after .env loading (may have been overridden)
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
    if emulator_host:
        print(f"   Environment: Local Emulator ({emulator_host})", file=sys.stderr)
    else:
        print(f"   Environment: Production ({project})", file=sys.stderr)

    # Database name must be explicitly set via environment variable
    database_name = os.getenv("FIRESTORE_DATABASE")
    if not database_name:
        print("❌ Error: FIRESTORE_DATABASE not set", file=sys.stderr)
        print("   For emulator: FIRESTORE_DATABASE=(default)", file=sys.stderr)
        print("   For production: FIRESTORE_DATABASE=strategy", file=sys.stderr)
        sys.exit(1)
    # Use None for "(default)" database (emulator limitation)
    database_name = None if database_name == "(default)" else database_name
    db = firestore.Client(project=project, database=database_name)
    collection = db.collection("archetypes")

    created = 0
    updated = 0

    for arch in archetypes:
        arch_id = arch.pop("id")  # Use id as Firestore document ID

        # Check if exists
        doc_ref = collection.document(arch_id)
        existing = doc_ref.get()

        if existing.exists:
            doc_ref.set(arch, merge=True)
            print(f"   ✅ Updated: {arch_id} ({arch.get('title')})", file=sys.stderr)
            updated += 1
        else:
            doc_ref.set(arch)
            print(f"   ✅ Created: {arch_id} ({arch.get('title')})", file=sys.stderr)
            created += 1

    print(
        f"✅ Successfully seeded {created + updated} archetypes ({created} created, {updated} updated)",
        file=sys.stderr,
    )
    return created, updated


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed archetypes into Firestore")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="GCP project ID (defaults to GOOGLE_CLOUD_PROJECT env var)",
    )

    args = parser.parse_args()

    # Set project if provided
    if args.project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = args.project

    try:
        seed_archetypes(dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Error seeding archetypes: {e}", file=sys.stderr)
        if args.dry_run is False:  # Only show traceback for real runs
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
