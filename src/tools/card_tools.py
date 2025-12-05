"""Card management tools for MCP server."""

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import RefResolver
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.db.card_repository import CardRepository
from src.db.strategy_repository import StrategyRepository
from src.models.card import Card
from src.models.strategy import Attachment
from src.tools.errors import (
    ErrorCode,
    StructuredToolError,
    not_found_error,
    schema_validation_error,
)


class CreateCardRequest(BaseModel):
    """Request for create_card tool (internal use only).

    Note: schema_etag is handled internally by MCP and not exposed in the public API.
    """

    type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')")
    slots: dict[str, Any] = Field(..., description="Slot values to validate and store")


class CreateCardResponse(BaseModel):
    """Response from create_card tool."""

    card_id: str = Field(..., description="Generated card identifier")
    type: str = Field(..., description="Archetype identifier")
    slots: dict[str, Any] = Field(..., description="Validated slot values")
    schema_etag: str = Field(..., description="Schema ETag used for validation")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")
    strategy_id: str | None = Field(
        None, description="Strategy ID if card was automatically attached"
    )
    attached: bool = Field(
        default=False, description="Whether card was attached to a strategy"
    )


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
    """Request for update_card tool (internal use only).

    Note: schema_etag is handled internally by MCP and not exposed in the public API.
    """

    card_id: str = Field(..., description="Card identifier")
    slots: dict[str, Any] = Field(..., description="Updated slot values")


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


class ValidateSlotsDraftResponse(BaseModel):
    """Response from validate_slots_draft tool."""

    type_id: str = Field(..., description="Archetype identifier")
    valid: bool = Field(..., description="Whether slots are valid")
    errors: list[str] = Field(
        default_factory=list, description="List of validation error messages (empty if valid)"
    )
    schema_etag: str = Field(
        ..., description="Schema ETag to use when creating card with these slots"
    )


def _validate_slots_against_schema(
    slots: dict[str, Any], schema: dict[str, Any], schema_repo: ArchetypeSchemaRepository
) -> list[str]:
    """Validate slots against JSON schema and return actionable error messages.

    This function handles external $ref references (e.g., to common_defs.schema.json)
    by loading the common definitions and using a RefResolver.

    Args:
        slots: Slot values to validate
        schema: JSON Schema to validate against
        schema_repo: Schema repository for additional context

    Returns:
        List of error messages (empty if validation passes)
    """
    errors = []

    # Load common_defs.json to resolve external $ref references
    # The schemas reference definitions like "common_defs.schema.json#/$defs/EntryActionSpec"
    project_root = Path(__file__).parent.parent.parent
    common_defs_path = project_root / "data" / "common_defs.json"

    try:
        with open(common_defs_path) as f:
            common_defs = json.load(f)
    except FileNotFoundError:
        # If common_defs.json doesn't exist, validation will fail on $ref resolution
        # This is fine - it will be caught by jsonschema and reported as an error
        common_defs = None

    # Create a resolver that can resolve references to common_defs
    # The store maps URI-like identifiers to their actual schema content
    store = {}
    if common_defs is not None:
        # Map "common_defs.schema.json" to the loaded JSON
        store["common_defs.schema.json"] = common_defs

    # Create resolver - it will use the store to resolve external references
    resolver = RefResolver.from_schema(schema, store=store) if store else None

    # Use jsonschema to validate with resolver for external $ref support
    try:
        if resolver:
            jsonschema.validate(instance=slots, schema=schema, resolver=resolver)
        else:
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


# Valid roles for card attachments (matching strategy_tools)
VALID_ROLES = ["entry", "gate", "exit", "sizing", "risk", "overlay"]


def register_card_tools(
    mcp: FastMCP,
    card_repo: CardRepository,
    schema_repo: ArchetypeSchemaRepository,
    strategy_repo: StrategyRepository | None = None,
) -> None:
    """Register all card management tools with the MCP server.

    Dependencies are injected so tests and callers can control which
    repositories (and therefore which databases/backends) are used.

    Args:
        mcp: FastMCP server instance
        card_repo: Card repository
        schema_repo: Schema repository
        strategy_repo: Strategy repository (optional, required for auto-attach feature)
    """

    @mcp.tool()
    def create_card(
        type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')"),
        slots: dict[str, Any] = Field(..., description="Slot values to validate and store"),  # noqa: B008
        strategy_id: str | None = Field(
            None, description="Optional strategy ID to automatically attach card to"
        ),
        role: str | None = Field(
            None,
            description="Card role (required if strategy_id provided): entry, gate, exit, sizing, risk, or overlay",
        ),
        overrides: dict[str, Any] = Field(  # noqa: B008
            default_factory=dict, description="Slot value overrides for attachment (optional)"
        ),
        follow_latest: bool = Field(
            default=False,
            description="If true, use latest card version; if false, pin current version (optional)",
        ),
        order: int | None = Field(
            None,
            description="Execution order (optional, auto-assigned if not provided)",
        ),
        enabled: bool = Field(
            default=True, description="Whether attachment is enabled (optional, default: true)"
        ),
    ) -> CreateCardResponse:
        """
        Create a new trading strategy card.

        Validates the provided slots against the archetype's JSON schema and stores
        the card in Firestore. The schema_etag is automatically set to the current
        schema version for version tracking (this is handled internally by MCP).

        If strategy_id is provided, the card will be automatically attached to the strategy
        with the specified role. This simplifies the workflow from two steps (create + attach)
        to a single step.

        Recommended workflow:
        1. Use get_archetypes to find available archetypes
        2. Use get_schema_example(type) to get ready-to-use example slots
        3. Optionally modify the example slots to fit your needs
        4. Call create_card with type, slots, and optionally strategy_id + role to create and attach in one step

        Args:
            type: Archetype identifier (e.g., 'entry.trend_pullback', 'exit.take_profit_stop', 'gate.regime', 'overlay.regime_scaler')
            slots: Slot values to validate and store. Must match the archetype's JSON schema.
            strategy_id: Optional strategy ID. If provided, card will be automatically attached.
            role: Card role (required if strategy_id provided): entry, gate, exit, sizing, risk, or overlay
            overrides: Slot value overrides to merge with card slots (optional, only used if strategy_id provided)
            follow_latest: If true, use latest card version; if false, pin current version (optional)
            order: Execution order (optional, auto-assigned if not provided)
            enabled: Whether attachment is enabled (optional, default: true)

        Returns:
            CreateCardResponse with generated card_id and validated data. If strategy_id was provided,
            the response will include strategy_id and attached=True.

        Raises:
            StructuredToolError: With error codes:
                - ARCHETYPE_NOT_FOUND: If archetype schema not found (non-retryable)
                - SCHEMA_VALIDATION_ERROR: If slot validation fails (non-retryable)
                - INVALID_ROLE: If role is invalid when strategy_id is provided (non-retryable)
                - STRATEGY_NOT_FOUND: If strategy not found when strategy_id is provided (non-retryable)
                - DUPLICATE_ATTACHMENT: If card is already attached to strategy (non-retryable)

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

        # Always use current schema etag - this is internal to MCP
        schema_etag = schema.etag

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

        # Auto-attach to strategy if strategy_id is provided
        attached = False
        if strategy_id is not None:
            if strategy_repo is None:
                raise StructuredToolError(
                    message="Strategy repository not available. Cannot attach card to strategy.",
                    error_code=ErrorCode.INTERNAL_ERROR,
                    retryable=False,
                    recovery_hint="Create card without strategy_id, then use attach_card separately.",
                    details={"strategy_id": strategy_id},
                )

            # Validate role is provided
            if role is None:
                raise StructuredToolError(
                    message="Role is required when strategy_id is provided.",
                    error_code=ErrorCode.INVALID_ROLE,
                    retryable=False,
                    recovery_hint=f"Provide a role from: {', '.join(VALID_ROLES)}",
                    details={"strategy_id": strategy_id, "valid_roles": VALID_ROLES},
                )

            # Validate role
            if role not in VALID_ROLES:
                raise StructuredToolError(
                    message=f"Invalid role: {role}. Must be one of: {VALID_ROLES}.",
                    error_code=ErrorCode.INVALID_ROLE,
                    retryable=False,
                    recovery_hint=f"Use one of: {', '.join(VALID_ROLES)}",
                    details={"provided_role": role, "valid_roles": VALID_ROLES},
                )

            # Get strategy
            strategy = strategy_repo.get_by_id(strategy_id)
            if strategy is None:
                raise not_found_error(
                    resource_type="Strategy",
                    resource_id=strategy_id,
                    recovery_hint="Use list_strategies to see all available strategies.",
                )

            # Check if card is already attached
            for att in strategy.attachments:
                if att.card_id == created_card.id:
                    raise StructuredToolError(
                        message=f"Card {created_card.id} is already attached to strategy {strategy_id}.",
                        error_code=ErrorCode.DUPLICATE_ATTACHMENT,
                        retryable=False,
                        recovery_hint="Create card without strategy_id, or use attach_card separately.",
                        details={"card_id": created_card.id, "strategy_id": strategy_id},
                    )

            # Determine order (auto-assign if not provided)
            attachment_order = order
            if attachment_order is None:
                if strategy.attachments:
                    max_order = max(att.order for att in strategy.attachments)
                    attachment_order = max_order + 1
                else:
                    attachment_order = 1

            # Determine card_revision_id (use updated_at as simple revision identifier for MVP)
            card_revision_id = None
            if not follow_latest:
                card_revision_id = created_card.updated_at  # Simple revision ID for MVP

            # Create attachment
            attachment = Attachment(
                card_id=created_card.id,
                role=role,
                order=attachment_order,
                enabled=enabled,
                overrides=overrides,
                follow_latest=follow_latest,
                card_revision_id=card_revision_id,
            )

            # Add attachment to strategy
            strategy.attachments.append(attachment)
            strategy_repo.update(strategy)
            attached = True

        return CreateCardResponse(
            card_id=created_card.id,
            type=created_card.type,
            slots=created_card.slots,
            schema_etag=created_card.schema_etag,
            created_at=created_card.created_at,
            strategy_id=strategy_id if attached else None,
            attached=attached,
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
    ) -> UpdateCardResponse:
        """
        Update an existing card's slots.

        Validates the updated slots against the archetype's JSON schema. The schema_etag
        is automatically updated to the current schema version (this is handled internally by MCP).

        Recommended workflow:
        1. Use get_card(card_id) to get the current card and its type
        2. Use get_archetype_schema(type) to get the schema, constraints, and examples
        3. Use the examples in the schema as a reference for valid slot values
        4. Call update_card with card_id and updated slots

        Args:
            card_id: Card identifier
            slots: Updated slot values. Must match the archetype's JSON schema.

        Returns:
            UpdateCardResponse with updated card data

        Raises:
            StructuredToolError: With error codes:
                - CARD_NOT_FOUND: If card not found (non-retryable)
                - ARCHETYPE_NOT_FOUND: If archetype schema not found (non-retryable)
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

        # Always use current schema etag - this is internal to MCP
        schema_etag = schema.etag

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

    @mcp.tool()
    def validate_slots_draft(
        type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')"),
        slots: dict[str, Any] = Field(..., description="Slot values to validate"),  # noqa: B008
    ) -> ValidateSlotsDraftResponse:
        """
        Validate slot values against an archetype schema without creating a card.

        This tool allows you to check if slot values are valid before creating a card.
        It's useful for iterating on slot configurations or validating user input.

        Recommended workflow:
        1. Use get_schema_example(type) to get a starting point
        2. Modify the example slots as needed
        3. Use validate_slots_draft(type, slots) to check validity
        4. If valid, use create_card with the slots (schema_etag is handled automatically)

        Args:
            type: Archetype identifier
            slots: Slot values to validate

        Returns:
            ValidateSlotsDraftResponse with validation result and errors (if any)

        Raises:
            StructuredToolError: With error code ARCHETYPE_NOT_FOUND if archetype schema not found (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Fetch schema for validation
        schema = schema_repo.get_by_type_id(type)
        if schema is None:
            raise not_found_error(
                resource_type="Archetype",
                resource_id=type,
                recovery_hint="Use get_archetypes to see available archetypes.",
            )

        # Validate slots against JSON schema
        validation_errors = _validate_slots_against_schema(slots, schema.json_schema, schema_repo)

        return ValidateSlotsDraftResponse(
            type_id=type,
            valid=len(validation_errors) == 0,
            errors=validation_errors,
            schema_etag=schema.etag,
        )
