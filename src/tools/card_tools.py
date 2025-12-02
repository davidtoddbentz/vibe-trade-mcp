"""Card management tools for MCP server."""

from typing import Any

import jsonschema
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.db.card_repository import CardRepository
from src.models.card import Card
from src.tools.errors import (
    not_found_error,
    schema_etag_mismatch_error,
    schema_validation_error,
)


class CreateCardRequest(BaseModel):
    """Request for create_card tool."""

    type: str = Field(..., description="Archetype identifier (e.g., 'signal.trend_pullback')")
    slots: dict[str, Any] = Field(..., description="Slot values to validate and store")
    schema_etag: str = Field(
        ..., description="ETag of the schema used for validation (must match current schema)"
    )


class CreateCardResponse(BaseModel):
    """Response from create_card tool."""

    card_id: str = Field(..., description="Generated card identifier")
    type: str = Field(..., description="Archetype identifier")
    slots: dict[str, Any] = Field(..., description="Validated slot values")
    schema_etag: str = Field(..., description="Schema ETag used for validation")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")


class GetCardRequest(BaseModel):
    """Request for get_card tool."""

    card_id: str = Field(..., description="Card identifier")


class GetCardResponse(BaseModel):
    """Response from get_card tool."""

    card_id: str = Field(..., description="Card identifier")
    type: str = Field(..., description="Archetype identifier")
    slots: dict[str, Any] = Field(..., description="Slot values")
    schema_etag: str = Field(..., description="Schema ETag")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class ListCardsResponse(BaseModel):
    """Response from list_cards tool."""

    cards: list[GetCardResponse] = Field(..., description="List of cards")
    count: int = Field(..., description="Total number of cards")


class UpdateCardRequest(BaseModel):
    """Request for update_card tool."""

    card_id: str = Field(..., description="Card identifier")
    slots: dict[str, Any] = Field(..., description="Updated slot values")
    schema_etag: str = Field(
        ..., description="ETag of the schema used for validation (must match current schema)"
    )


class UpdateCardResponse(BaseModel):
    """Response from update_card tool."""

    card_id: str = Field(..., description="Card identifier")
    type: str = Field(..., description="Archetype identifier")
    slots: dict[str, Any] = Field(..., description="Updated slot values")
    schema_etag: str = Field(..., description="Schema ETag")
    updated_at: str = Field(..., description="ISO8601 timestamp of update")


class DeleteCardRequest(BaseModel):
    """Request for delete_card tool."""

    card_id: str = Field(..., description="Card identifier")


class DeleteCardResponse(BaseModel):
    """Response from delete_card tool."""

    card_id: str = Field(..., description="Deleted card identifier")
    success: bool = Field(..., description="Whether deletion was successful")


def _validate_slots_against_schema(
    slots: dict[str, Any], schema: dict[str, Any], schema_repo: ArchetypeSchemaRepository
) -> list[str]:
    """Validate slots against JSON schema and return actionable error messages.

    Args:
        slots: Slot values to validate
        schema: JSON Schema to validate against
        schema_repo: Schema repository for additional context

    Returns:
        List of error messages (empty if validation passes)
    """
    errors = []

    # Use jsonschema to validate
    try:
        jsonschema.validate(instance=slots, schema=schema)
    except jsonschema.ValidationError as e:
        # Extract actionable error message
        path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        error_msg = f"Validation error at '{path}': {e.message}"
        if e.absolute_path:
            # Try to get more context from schema
            prop_schema = schema
            for segment in e.absolute_path:
                if isinstance(prop_schema, dict) and "properties" in prop_schema:
                    prop_schema = prop_schema["properties"].get(segment, {})
                else:
                    break

            # Add helpful hints if available
            if isinstance(prop_schema, dict):
                if "enum" in prop_schema:
                    error_msg += f" (must be one of: {prop_schema['enum']})"
                if "minimum" in prop_schema or "maximum" in prop_schema:
                    min_val = prop_schema.get("minimum")
                    max_val = prop_schema.get("maximum")
                    if min_val is not None and max_val is not None:
                        error_msg += f" (must be between {min_val} and {max_val})"
                    elif min_val is not None:
                        error_msg += f" (must be >= {min_val})"
                    elif max_val is not None:
                        error_msg += f" (must be <= {max_val})"

        errors.append(error_msg)

    return errors


def register_card_tools(
    mcp: FastMCP,
    card_repo: CardRepository,
    schema_repo: ArchetypeSchemaRepository,
) -> None:
    """Register all card management tools with the MCP server.

    Dependencies are injected so tests and callers can control which
    repositories (and therefore which databases/backends) are used.
    """

    @mcp.tool()
    def create_card(
        type: str = Field(..., description="Archetype identifier (e.g., 'signal.trend_pullback')"),
        slots: dict[str, Any] = Field(..., description="Slot values to validate and store"),  # noqa: B008
        schema_etag: str = Field(
            ...,
            description="ETag of the schema used for validation (must match current schema). Get this from get_archetype_schema.",
        ),
    ) -> CreateCardResponse:
        """
        Create a new trading strategy card.

        Validates the provided slots against the archetype's JSON schema and stores
        the card in Firestore. The schema_etag must match the current schema version
        to ensure the card was validated against the correct schema.

        Recommended workflow:
        1. Use get_archetypes to find available archetypes
        2. Use get_archetype_schema(type) to get the schema, constraints, examples, and schema_etag
        3. Use the examples in the schema as a reference for valid slot values
        4. Use the schema_etag from step 2 when creating the card

        Args:
            type: Archetype identifier (e.g., 'signal.trend_pullback')
            slots: Slot values to validate and store. Must match the archetype's JSON schema.
            schema_etag: ETag from get_archetype_schema (proves you validated against the correct schema version)

        Returns:
            CreateCardResponse with generated card_id and validated data

        Raises:
            StructuredToolError: With error codes:
                - ARCHETYPE_NOT_FOUND: If archetype schema not found (non-retryable)
                - SCHEMA_ETAG_MISMATCH: If schema_etag doesn't match current schema (non-retryable)
                - SCHEMA_VALIDATION_ERROR: If slot validation fails (non-retryable)

        Error Handling:
            All errors include structured information:
            - error_code: Machine-readable error code for conditional logic
            - retryable: Boolean indicating if the error is retryable
            - recovery_hint: Actionable guidance for recovery
            - details: Additional context (resource IDs, validation errors, etc.)
        """
        # Fetch schema for validation
        schema = schema_repo.get_by_type_id(type)
        if schema is None:
            raise not_found_error(
                resource_type="Archetype",
                resource_id=type,
                recovery_hint="Use get_archetypes to see available archetypes.",
            )

        # Verify schema_etag matches current schema
        if schema_etag != schema.etag:
            raise schema_etag_mismatch_error(
                provided_etag=schema_etag,
                current_etag=schema.etag,
                recovery_hint="Please fetch the latest schema with get_archetype_schema.",
            )

        # Validate slots against JSON schema
        validation_errors = _validate_slots_against_schema(slots, schema.json_schema, schema_repo)
        if validation_errors:
            raise schema_validation_error(
                type_id=type,
                errors=validation_errors,
                recovery_hint=f"Use get_archetype_schema('{type}') to see valid values, constraints, and examples.",
            )

        # Create card
        card = Card(
            id="",  # Will be generated by Firestore
            type=type,
            slots=slots,
            schema_etag=schema_etag,
            created_at="",  # Will be set by repository
            updated_at="",  # Will be set by repository
        )

        created_card = card_repo.create(card)

        return CreateCardResponse(
            card_id=created_card.id,
            type=created_card.type,
            slots=created_card.slots,
            schema_etag=created_card.schema_etag,
            created_at=created_card.created_at,
        )

    @mcp.tool()
    def get_card(card_id: str = Field(..., description="Card identifier")) -> GetCardResponse:
        """
        Get a card by ID.

        Args:
            card_id: Card identifier

        Returns:
            GetCardResponse with card data

        Raises:
            StructuredToolError: With error code CARD_NOT_FOUND if card not found (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        card = card_repo.get_by_id(card_id)
        if card is None:
            raise not_found_error(
                resource_type="Card",
                resource_id=card_id,
                recovery_hint="Use list_cards to see all available cards.",
            )

        return GetCardResponse(
            card_id=card.id,
            type=card.type,
            slots=card.slots,
            schema_etag=card.schema_etag,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )

    @mcp.tool()
    def list_cards() -> ListCardsResponse:
        """
        List all cards.

        Returns:
            ListCardsResponse with all cards
        """
        cards = card_repo.get_all()
        card_responses = [
            GetCardResponse(
                card_id=card.id,
                type=card.type,
                slots=card.slots,
                schema_etag=card.schema_etag,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
            for card in cards
        ]

        return ListCardsResponse(cards=card_responses, count=len(card_responses))

    @mcp.tool()
    def update_card(
        card_id: str = Field(..., description="Card identifier"),
        slots: dict[str, Any] = Field(..., description="Updated slot values"),  # noqa: B008
        schema_etag: str = Field(
            ...,
            description="ETag of the schema used for validation (must match current schema). Get this from get_archetype_schema.",
        ),
    ) -> UpdateCardResponse:
        """
        Update an existing card's slots.

        Validates the updated slots against the archetype's JSON schema. The schema_etag
        must match the current schema version.

        Recommended workflow:
        1. Use get_card(card_id) to get the current card and its type
        2. Use get_archetype_schema(type) to get the schema, constraints, examples, and schema_etag
        3. Use the examples in the schema as a reference for valid slot values
        4. Use the schema_etag from step 2 when updating the card

        Args:
            card_id: Card identifier
            slots: Updated slot values. Must match the archetype's JSON schema.
            schema_etag: ETag from get_archetype_schema (proves you validated against the correct schema version)

        Returns:
            UpdateCardResponse with updated card data

        Raises:
            StructuredToolError: With error codes:
                - CARD_NOT_FOUND: If card not found (non-retryable)
                - ARCHETYPE_NOT_FOUND: If archetype schema not found (non-retryable)
                - SCHEMA_ETAG_MISMATCH: If schema_etag doesn't match current schema (non-retryable)
                - SCHEMA_VALIDATION_ERROR: If slot validation fails (non-retryable)

        Error Handling:
            All errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Get existing card to get the type
        existing_card = card_repo.get_by_id(card_id)
        if existing_card is None:
            raise not_found_error(
                resource_type="Card",
                resource_id=card_id,
                recovery_hint="Use list_cards to see all available cards.",
            )

        # Fetch schema for validation
        schema = schema_repo.get_by_type_id(existing_card.type)
        if schema is None:
            raise not_found_error(
                resource_type="Archetype",
                resource_id=existing_card.type,
                recovery_hint="Use get_archetypes to see available archetypes.",
            )

        # Verify schema_etag matches current schema
        if schema_etag != schema.etag:
            raise schema_etag_mismatch_error(
                provided_etag=schema_etag,
                current_etag=schema.etag,
                recovery_hint="Please fetch the latest schema with get_archetype_schema.",
            )

        # Validate slots against JSON schema
        validation_errors = _validate_slots_against_schema(slots, schema.json_schema, schema_repo)
        if validation_errors:
            raise schema_validation_error(
                type_id=existing_card.type,
                errors=validation_errors,
                recovery_hint=f"Use get_archetype_schema('{existing_card.type}') to see valid values, constraints, and examples.",
            )

        # Update card
        updated_card = Card(
            id=card_id,
            type=existing_card.type,
            slots=slots,
            schema_etag=schema_etag,
            created_at=existing_card.created_at,
            updated_at="",  # Will be set by repository
        )

        updated = card_repo.update(updated_card)

        return UpdateCardResponse(
            card_id=updated.id,
            type=updated.type,
            slots=updated.slots,
            schema_etag=updated.schema_etag,
            updated_at=updated.updated_at,
        )

    @mcp.tool()
    def delete_card(card_id: str = Field(..., description="Card identifier")) -> DeleteCardResponse:
        """
        Delete a card by ID.

        Args:
            card_id: Card identifier

        Returns:
            DeleteCardResponse confirming deletion

        Raises:
            StructuredToolError: With error code CARD_NOT_FOUND if card not found (non-retryable)
        """
        try:
            card_repo.delete(card_id)
            return DeleteCardResponse(card_id=card_id, success=True)
        except ValueError as e:
            raise not_found_error(
                resource_type="Card",
                resource_id=card_id,
                recovery_hint="Use list_cards to see all available cards.",
            ) from e
