"""Strategy management tools for MCP server."""

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.db.archetype_schema_repository import ArchetypeSchemaRepository
from src.db.card_repository import CardRepository
from src.db.strategy_repository import StrategyRepository
from src.models.card import Card
from src.models.strategy import Attachment, Strategy
from src.tools.card_tools import _validate_slots_against_schema
from src.tools.errors import (
    ErrorCode,
    StructuredToolError,
    not_found_error,
    validation_error,
)

# Valid roles for card attachments
VALID_ROLES = ["signal", "gate", "exit", "sizing", "risk", "overlay"]
VALID_STATUSES = ["draft", "ready", "running", "paused", "stopped", "error"]


class CreateStrategyResponse(BaseModel):
    """Response from create_strategy tool."""

    strategy_id: str = Field(..., description="Generated strategy identifier")
    name: str = Field(..., description="Strategy name")
    status: str = Field(..., description="Strategy status")
    universe: list[str] = Field(..., description="Trading universe")
    attachments: list[dict[str, Any]] = Field(..., description="Attached cards")
    version: int = Field(..., description="Strategy version")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")


class GetStrategyResponse(BaseModel):
    """Response from get_strategy tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    owner_id: str | None = Field(None, description="Owner identifier")
    name: str = Field(..., description="Strategy name")
    status: str = Field(..., description="Strategy status")
    universe: list[str] = Field(..., description="Trading universe")
    attachments: list[dict[str, Any]] = Field(..., description="Attached cards")
    version: int = Field(..., description="Strategy version")
    created_at: str = Field(..., description="ISO8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class UpdateStrategyMetaResponse(BaseModel):
    """Response from update_strategy_meta tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    name: str = Field(..., description="Strategy name")
    status: str = Field(..., description="Strategy status")
    universe: list[str] = Field(..., description="Trading universe")
    version: int = Field(..., description="Strategy version")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class AttachCardResponse(BaseModel):
    """Response from attach_card tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    attachments: list[dict[str, Any]] = Field(..., description="Updated attachments list")
    version: int = Field(..., description="Strategy version")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class DetachCardResponse(BaseModel):
    """Response from detach_card tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    attachments: list[dict[str, Any]] = Field(..., description="Updated attachments list")
    version: int = Field(..., description="Strategy version")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class ListStrategiesResponse(BaseModel):
    """Response from list_strategies tool."""

    strategies: list[dict[str, Any]] = Field(..., description="List of strategies")
    count: int = Field(..., description="Total number of strategies")


class CompiledCard(BaseModel):
    """Compiled card with effective slots."""

    role: str = Field(..., description="Card role")
    card_id: str = Field(..., description="Card identifier")
    card_revision_id: str | None = Field(None, description="Card revision identifier")
    type: str = Field(..., description="Archetype type")
    effective_slots: dict[str, Any] = Field(..., description="Merged slots (card + overrides)")


class DataRequirement(BaseModel):
    """Data requirement for a symbol/timeframe combination."""

    symbol: str = Field(..., description="Trading symbol")
    tf: str = Field(..., description="Timeframe")
    min_bars: int = Field(..., description="Minimum history bars required")
    lookback_hours: float = Field(..., description="Lookback time in hours")


class Issue(BaseModel):
    """Validation issue found during compilation."""

    severity: str = Field(..., description="Issue severity: error or warning")
    code: str = Field(..., description="Issue code")
    message: str = Field(..., description="Human-readable message")
    path: str | None = Field(None, description="Path to the problematic element")


class CompiledStrategy(BaseModel):
    """Compiled strategy plan."""

    strategy_id: str = Field(..., description="Strategy identifier")
    universe: list[str] = Field(..., description="Trading universe")
    cards: list[CompiledCard] = Field(..., description="Compiled cards with effective slots")
    data_requirements: list[DataRequirement] = Field(..., description="Data requirements")


class CompileStrategyResponse(BaseModel):
    """Response from compile_strategy tool."""

    status_hint: str = Field(..., description="Status: ready or fix_required")
    compiled: CompiledStrategy | None = Field(None, description="Compiled strategy (if ready)")
    issues: list[Issue] = Field(default_factory=list, description="Validation issues")
    validation_summary: dict[str, int] = Field(
        default_factory=lambda: {"errors": 0, "warnings": 0, "cards_validated": 0},
        description="Summary of validation: error count, warning count, and number of cards validated",
    )


def register_strategy_tools(
    mcp: FastMCP,
    strategy_repo: StrategyRepository,
    card_repo: CardRepository,
    schema_repo: ArchetypeSchemaRepository,
) -> None:
    """Register all strategy management tools with the MCP server.

    Dependencies are injected so tests and callers can control which
    repositories (and therefore which databases/backends) are used.
    """

    @mcp.tool()
    def create_strategy(
        name: str = Field(..., description="Strategy name"),
        owner_id: str | None = Field(None, description="Owner identifier (optional)"),
        universe: list[str] = Field(  # noqa: B008
            default_factory=list, description="Trading universe symbols"
        ),
    ) -> CreateStrategyResponse:
        """
        Create a new trading strategy.

        A strategy is a composition of cards (signals, gates, exits, etc.) with
        universe selection. Risk and execution parameters are configured when
        the strategy is run, not at creation time.

        Recommended workflow:
        1. Create cards using create_card tool
        2. Create strategy with create_strategy
        3. Attach cards to strategy using attach_card

        Args:
            name: Strategy name
            owner_id: Owner identifier (optional)
            universe: List of trading symbols (e.g., ['BTC-USD'])

        Returns:
            CreateStrategyResponse with generated strategy_id and initial configuration
        """
        # Create strategy
        strategy = Strategy(
            id="",  # Will be generated by Firestore
            owner_id=owner_id,
            name=name,
            status="draft",
            universe=universe,
            attachments=[],
            version=1,
            created_at="",  # Will be set by repository
            updated_at="",  # Will be set by repository
        )

        created_strategy = strategy_repo.create(strategy)

        return CreateStrategyResponse(
            strategy_id=created_strategy.id,
            name=created_strategy.name,
            status=created_strategy.status,
            universe=created_strategy.universe,
            attachments=[att.model_dump() for att in created_strategy.attachments],
            version=created_strategy.version,
            created_at=created_strategy.created_at,
        )

    @mcp.tool()
    def get_strategy(
        strategy_id: str = Field(..., description="Strategy identifier"),
    ) -> GetStrategyResponse:
        """
        Get a strategy by ID.

        Args:
            strategy_id: Strategy identifier

        Returns:
            GetStrategyResponse with strategy data

        Raises:
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        return GetStrategyResponse(
            strategy_id=strategy.id,
            owner_id=strategy.owner_id,
            name=strategy.name,
            status=strategy.status,
            universe=strategy.universe,
            attachments=[att.model_dump() for att in strategy.attachments],
            version=strategy.version,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )

    @mcp.tool()
    def update_strategy_meta(
        strategy_id: str = Field(..., description="Strategy identifier"),
        name: str | None = Field(None, description="Strategy name (optional)"),
        status: str | None = Field(None, description="Strategy status (optional)"),
        universe: list[str] | None = Field(None, description="Trading universe (optional)"),  # noqa: B008
    ) -> UpdateStrategyMetaResponse:
        """
        Update strategy metadata.

        Updates only the fields provided. Other fields remain unchanged.

        Args:
            strategy_id: Strategy identifier
            name: Strategy name (optional)
            status: Strategy status: draft, ready, running, paused, stopped, error (optional)
            universe: Trading universe symbols (optional)

        Returns:
            UpdateStrategyMetaResponse with updated strategy data

        Raises:
            StructuredToolError: With error codes:
                - STRATEGY_NOT_FOUND: If strategy not found (non-retryable)
                - INVALID_STATUS: If status is invalid (non-retryable)
        """
        # Get existing strategy
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        # Validate status if provided
        if status is not None and status not in VALID_STATUSES:
            raise StructuredToolError(
                message=f"Invalid status: {status}. Must be one of: {VALID_STATUSES}.",
                error_code=ErrorCode.INVALID_STATUS,
                retryable=False,
                recovery_hint=f"Use one of: {', '.join(VALID_STATUSES)}",
                details={"provided_status": status, "valid_statuses": VALID_STATUSES},
            )

        # Update only provided fields
        if name is not None:
            strategy.name = name
        if status is not None:
            strategy.status = status
        if universe is not None:
            strategy.universe = universe

        updated_strategy = strategy_repo.update(strategy)

        return UpdateStrategyMetaResponse(
            strategy_id=updated_strategy.id,
            name=updated_strategy.name,
            status=updated_strategy.status,
            universe=updated_strategy.universe,
            version=updated_strategy.version,
            updated_at=updated_strategy.updated_at,
        )

    @mcp.tool()
    def attach_card(
        strategy_id: str = Field(..., description="Strategy identifier"),
        card_id: str = Field(..., description="Card identifier to attach"),
        role: str = Field(
            ...,
            description="Card role: signal, gate, exit, sizing, risk, or overlay",
        ),
        overrides: dict[str, Any] = Field(  # noqa: B008
            default_factory=dict, description="Slot value overrides (optional)"
        ),
        follow_latest: bool = Field(
            default=False,
            description="If true, use latest card version; if false, pin current version",
        ),
        order: int | None = Field(
            None,
            description="Execution order (optional, auto-assigned if not provided)",
        ),
        enabled: bool = Field(default=True, description="Whether attachment is enabled"),
    ) -> AttachCardResponse:
        """
        Attach a card to a strategy.

        Cards can be attached with different roles (signal, gate, exit, etc.) and
        optional slot overrides. The attachment can follow the latest card version
        or be pinned to a specific version.

        Recommended workflow:
        1. Create cards using create_card
        2. Create strategy using create_strategy
        3. Attach cards using attach_card with appropriate roles
        4. Use validate_strategy or compile_strategy to check for issues

        Args:
            strategy_id: Strategy identifier
            card_id: Card identifier to attach
            role: Card role (signal, gate, exit, sizing, risk, or overlay)
            overrides: Slot value overrides to merge with card slots (optional).
                Overrides use deep merge: nested objects are merged recursively,
                not replaced. For example, if card has {"context": {"symbol": "BTC-USD", "tf": "1h"}}
                and you provide {"context": {"tf": "4h"}}, the result is
                {"context": {"symbol": "BTC-USD", "tf": "4h"}} (tf is updated, symbol is preserved).
                To replace an entire nested object, you must provide all its fields.
            follow_latest: If true, use latest card version; if false, pin current version
            order: Execution order (optional, auto-assigned to next available)
            enabled: Whether attachment is enabled (default: true)

        Returns:
            AttachCardResponse with updated attachments list

        Raises:
            StructuredToolError: With error codes:
                - INVALID_ROLE: If role is invalid (non-retryable)
                - STRATEGY_NOT_FOUND: If strategy not found (non-retryable)
                - CARD_NOT_FOUND: If card not found (non-retryable)
                - DUPLICATE_ATTACHMENT: If card is already attached (non-retryable)

        Error Handling:
            All errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Validate role
        if role not in VALID_ROLES:
            raise StructuredToolError(
                message=f"Invalid role: {role}. Must be one of: {VALID_ROLES}.",
                error_code=ErrorCode.INVALID_ROLE,
                retryable=False,
                recovery_hint=f"Use one of: {', '.join(VALID_ROLES)}. Use get_strategy to see current attachments.",
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

        # Verify card exists
        card = card_repo.get_by_id(card_id)
        if card is None:
            raise not_found_error(
                resource_type="Card",
                resource_id=card_id,
                recovery_hint="Use list_cards to see all available cards.",
            )

        # Check if card is already attached
        for att in strategy.attachments:
            if att.card_id == card_id:
                raise validation_error(
                    message=f"Card {card_id} is already attached to strategy {strategy_id}.",
                    recovery_hint="Use detach_card first to remove it, or update the attachment manually.",
                    details={"card_id": card_id, "strategy_id": strategy_id},
                )

        # Determine order (auto-assign if not provided)
        if order is None:
            if strategy.attachments:
                max_order = max(att.order for att in strategy.attachments)
                order = max_order + 1
            else:
                order = 1

        # Determine card_revision_id (use updated_at as simple revision identifier for MVP)
        card_revision_id = None
        if not follow_latest:
            card_revision_id = card.updated_at  # Simple revision ID for MVP

        # Create attachment
        attachment = Attachment(
            card_id=card_id,
            role=role,
            order=order,
            enabled=enabled,
            overrides=overrides,
            follow_latest=follow_latest,
            card_revision_id=card_revision_id,
        )

        # Add attachment to strategy
        strategy.attachments.append(attachment)
        updated_strategy = strategy_repo.update(strategy)

        return AttachCardResponse(
            strategy_id=updated_strategy.id,
            attachments=[att.model_dump() for att in updated_strategy.attachments],
            version=updated_strategy.version,
            updated_at=updated_strategy.updated_at,
        )

    @mcp.tool()
    def detach_card(
        strategy_id: str = Field(..., description="Strategy identifier"),
        card_id: str = Field(..., description="Card identifier to detach"),
    ) -> DetachCardResponse:
        """
        Detach a card from a strategy.

        Args:
            strategy_id: Strategy identifier
            card_id: Card identifier to detach

        Returns:
            DetachCardResponse with updated attachments list

        Raises:
            StructuredToolError: With error codes:
                - STRATEGY_NOT_FOUND: If strategy not found (non-retryable)
                - ATTACHMENT_NOT_FOUND: If card is not attached (non-retryable)
        """
        # Get strategy
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        # Find and remove attachment
        original_count = len(strategy.attachments)
        strategy.attachments = [att for att in strategy.attachments if att.card_id != card_id]

        if len(strategy.attachments) == original_count:
            raise validation_error(
                message=f"Card {card_id} is not attached to strategy {strategy_id}.",
                recovery_hint="Use get_strategy to see current attachments.",
                details={"card_id": card_id, "strategy_id": strategy_id},
            )

        updated_strategy = strategy_repo.update(strategy)

        return DetachCardResponse(
            strategy_id=updated_strategy.id,
            attachments=[att.model_dump() for att in updated_strategy.attachments],
            version=updated_strategy.version,
            updated_at=updated_strategy.updated_at,
        )

    @mcp.tool()
    def list_strategies() -> ListStrategiesResponse:
        """
        List all strategies.

        Returns:
            ListStrategiesResponse with all strategies
        """
        strategies = strategy_repo.get_all()
        strategy_dicts = []
        for strategy in strategies:
            strategy_dicts.append(
                {
                    "strategy_id": strategy.id,
                    "owner_id": strategy.owner_id,
                    "name": strategy.name,
                    "status": strategy.status,
                    "universe": strategy.universe,
                    "attachments_count": len(strategy.attachments),
                    "version": strategy.version,
                    "created_at": strategy.created_at,
                    "updated_at": strategy.updated_at,
                }
            )

        return ListStrategiesResponse(strategies=strategy_dicts, count=len(strategy_dicts))

    @mcp.tool()
    def validate_strategy(
        strategy_id: str = Field(..., description="Strategy identifier to validate"),
    ) -> CompileStrategyResponse:
        """
        Validate a strategy without compiling it into a runnable plan.

        This tool performs the same validation checks as compile_strategy but
        doesn't return a compiled plan. It's useful for quick validation checks
        or when you want to see issues without the overhead of compilation.

        Recommended workflow:
        1. Create/update strategy and attach cards
        2. Call validate_strategy to check for issues
        3. If status_hint is 'fix_required', address issues and re-validate
        4. Once ready, use compile_strategy to get the compiled plan

        Args:
            strategy_id: The ID of the strategy to validate

        Returns:
            CompileStrategyResponse: Contains status_hint, issues, and validation_summary.
            The compiled field will be None since this is validation-only.

        Raises:
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found (non-retryable)
        """
        # Get strategy
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        # Reuse the same validation logic as compile_strategy
        # We'll build issues and validation summary but skip the compiled plan
        issues: list[Issue] = []
        compiled_cards: list[CompiledCard] = []
        data_requirements_map: dict[tuple[str, str], int] = {}  # (symbol, tf) -> min_bars

        # Process attachments (same logic as compile_strategy)
        for attachment in strategy.attachments:
            card: Card | None = None
            card_revision_id: str | None = None

            if attachment.follow_latest:
                card = card_repo.get_by_id(attachment.card_id)
                if card is None:
                    issues.append(
                        Issue(
                            severity="error",
                            code="CARD_NOT_FOUND",
                            message=f"Attached card '{attachment.card_id}' not found.",
                            path=f"attachments[{attachment.card_id}]",
                        )
                    )
                    continue
            else:
                current_card = card_repo.get_by_id(attachment.card_id)
                if current_card and current_card.updated_at == attachment.card_revision_id:
                    card = current_card
                    card_revision_id = attachment.card_revision_id
                else:
                    issues.append(
                        Issue(
                            severity="error",
                            code="CARD_REVISION_NOT_FOUND",
                            message=f"Pinned card revision for card '{attachment.card_id}' (revision '{attachment.card_revision_id}') not found or does not match current card's updated_at.",
                            path=f"attachments[{attachment.card_id}]",
                        )
                    )
                    continue

            # Merge card.slots with attachment.overrides
            effective_slots = card.slots.copy()
            if attachment.overrides:
                # Deep merge overrides
                def deep_merge(base: dict, override: dict) -> dict:
                    result = base.copy()
                    for key, value in override.items():
                        if (
                            key in result
                            and isinstance(result[key], dict)
                            and isinstance(value, dict)
                        ):
                            result[key] = deep_merge(result[key], value)
                        else:
                            result[key] = value
                    return result

                effective_slots = deep_merge(effective_slots, attachment.overrides)

            # Get schema for validation and data requirements
            schema = schema_repo.get_by_type_id(card.type)
            if schema is None:
                issues.append(
                    Issue(
                        severity="error",
                        code="SCHEMA_NOT_FOUND",
                        message=f"Schema for archetype {card.type} not found",
                        path=f"attachments[{attachment.card_id}].type",
                    )
                )
                continue

            # Validate effective slots against schema (after merging overrides)
            validation_errors = _validate_slots_against_schema(
                effective_slots, schema.json_schema, schema_repo
            )
            if validation_errors:
                # Format validation errors into issues
                for error_msg in validation_errors:
                    issues.append(
                        Issue(
                            severity="error",
                            code="SLOT_VALIDATION_ERROR",
                            message=f"Effective slots for card '{attachment.card_id}' (type '{card.type}') failed schema validation: {error_msg}",
                            path=f"attachments[{attachment.card_id}].effective_slots",
                        )
                    )
                # Continue processing other cards even if this one fails validation
                continue

            # Extract symbol and timeframe from effective_slots
            symbol = None
            tf = None
            if "context" in effective_slots:
                context = effective_slots["context"]
                symbol = context.get("symbol")
                tf = context.get("tf")

            if not symbol or not tf:
                issues.append(
                    Issue(
                        severity="error",
                        code="MISSING_CONTEXT",
                        message=f"Card {attachment.card_id} missing symbol or tf in context",
                        path=f"attachments[{attachment.card_id}].effective_slots.context",
                    )
                )
                continue

            # Compute data requirements
            min_bars = schema.constraints.min_history_bars or 100  # Default fallback
            key = (symbol, tf)
            if key not in data_requirements_map or min_bars > data_requirements_map[key]:
                data_requirements_map[key] = min_bars

            # Create compiled card (for validation summary)
            compiled_cards.append(
                CompiledCard(
                    role=attachment.role,
                    card_id=attachment.card_id,
                    card_revision_id=card_revision_id,
                    type=card.type,
                    effective_slots=effective_slots,
                )
            )

        # Validate composition
        signal_count = sum(1 for card in compiled_cards if card.role == "signal")
        exit_count = sum(1 for card in compiled_cards if card.role == "exit")

        if signal_count == 0:
            issues.append(
                Issue(
                    severity="error",
                    code="NO_SIGNALS",
                    message="Strategy has no signal cards attached",
                    path="attachments",
                )
            )

        if exit_count == 0:
            issues.append(
                Issue(
                    severity="warning",
                    code="NO_EXITS",
                    message="Strategy has no exit cards attached (positions may not close automatically)",
                    path="attachments",
                )
            )

        if exit_count > 1:
            issues.append(
                Issue(
                    severity="warning",
                    code="MULTIPLE_EXITS",
                    message=f"Strategy has {exit_count} exit cards (may cause conflicts)",
                    path="attachments",
                )
            )

        # Determine status
        error_count = sum(1 for issue in issues if issue.severity == "error")
        status_hint = "ready" if error_count == 0 else "fix_required"

        # Calculate validation summary
        warning_count = sum(1 for i in issues if i.severity == "warning")
        cards_validated = len(compiled_cards)

        return CompileStrategyResponse(
            status_hint=status_hint,
            compiled=None,  # Validation-only, no compiled plan
            issues=issues,
            validation_summary={
                "errors": error_count,
                "warnings": warning_count,
                "cards_validated": cards_validated,
            },
        )

    @mcp.tool()
    def compile_strategy(
        strategy_id: str = Field(..., description="Strategy identifier"),
    ) -> CompileStrategyResponse:
        """
        Compile and validate a strategy into a runnable plan.

        This tool performs preflight checks and resolves all cards into their effective
        configurations. It validates composition, computes data requirements, and reports
        any issues that need to be fixed before the strategy can run.

        Recommended workflow:
        1. Create cards using create_card
        2. Create strategy using create_strategy
        3. Attach cards using attach_card
        4. Compile strategy using compile_strategy to validate and get data requirements
        5. Fix any issues reported
        6. Re-compile until status_hint is "ready"

        Args:
            strategy_id: Strategy identifier

        Returns:
            CompileStrategyResponse with status_hint, compiled plan, and issues

        Raises:
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found (non-retryable)

        Error Handling:
            Errors include structured information with error_code, retryable flag,
            recovery_hint, and details for agentic decision-making.
        """
        # Get strategy
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        issues: list[Issue] = []
        compiled_cards: list[CompiledCard] = []
        data_requirements_map: dict[tuple[str, str], int] = {}  # (symbol, tf) -> max min_bars

        # Resolve and compile each attachment
        for attachment in strategy.attachments:
            if not attachment.enabled:
                continue

            # Resolve card (handle follow_latest vs pinned)
            if attachment.follow_latest:
                card = card_repo.get_by_id(attachment.card_id)
                if card is None:
                    issues.append(
                        Issue(
                            severity="error",
                            code="CARD_NOT_FOUND",
                            message=f"Card {attachment.card_id} not found (follow_latest=true)",
                            path=f"attachments[{attachment.card_id}]",
                        )
                    )
                    continue
                card_revision_id = card.updated_at
            else:
                # For pinned cards, we'd need to fetch by revision_id
                # For MVP, we'll just get the latest and use the stored revision_id
                card = card_repo.get_by_id(attachment.card_id)
                if card is None:
                    issues.append(
                        Issue(
                            severity="error",
                            code="CARD_NOT_FOUND",
                            message=f"Card {attachment.card_id} not found",
                            path=f"attachments[{attachment.card_id}]",
                        )
                    )
                    continue
                # In a full implementation, we'd validate card.updated_at matches card_revision_id
                card_revision_id = attachment.card_revision_id

            # Merge card.slots with attachment.overrides
            effective_slots = card.slots.copy()
            if attachment.overrides:
                # Deep merge overrides
                def deep_merge(base: dict, override: dict) -> dict:
                    result = base.copy()
                    for key, value in override.items():
                        if (
                            key in result
                            and isinstance(result[key], dict)
                            and isinstance(value, dict)
                        ):
                            result[key] = deep_merge(result[key], value)
                        else:
                            result[key] = value
                    return result

                effective_slots = deep_merge(effective_slots, attachment.overrides)

            # Get schema for validation and data requirements
            schema = schema_repo.get_by_type_id(card.type)
            if schema is None:
                issues.append(
                    Issue(
                        severity="error",
                        code="SCHEMA_NOT_FOUND",
                        message=f"Schema for archetype {card.type} not found",
                        path=f"attachments[{attachment.card_id}].type",
                    )
                )
                continue

            # Validate effective slots against schema (after merging overrides)
            validation_errors = _validate_slots_against_schema(
                effective_slots, schema.json_schema, schema_repo
            )
            if validation_errors:
                # Format validation errors into issues
                for error_msg in validation_errors:
                    issues.append(
                        Issue(
                            severity="error",
                            code="SLOT_VALIDATION_ERROR",
                            message=f"Effective slots for card '{attachment.card_id}' (type '{card.type}') failed schema validation: {error_msg}",
                            path=f"attachments[{attachment.card_id}].effective_slots",
                        )
                    )
                # Continue processing other cards even if this one fails validation
                continue

            # Extract symbol and timeframe from effective_slots
            symbol = None
            tf = None
            if "context" in effective_slots:
                context = effective_slots["context"]
                symbol = context.get("symbol")
                tf = context.get("tf")

            if not symbol or not tf:
                issues.append(
                    Issue(
                        severity="error",
                        code="MISSING_CONTEXT",
                        message=f"Card {attachment.card_id} missing symbol or tf in context",
                        path=f"attachments[{attachment.card_id}].effective_slots.context",
                    )
                )
                continue

            # Compute data requirements
            min_bars = schema.constraints.min_history_bars or 100  # Default fallback
            key = (symbol, tf)
            if key not in data_requirements_map or min_bars > data_requirements_map[key]:
                data_requirements_map[key] = min_bars

            # Create compiled card
            compiled_cards.append(
                CompiledCard(
                    role=attachment.role,
                    card_id=attachment.card_id,
                    card_revision_id=card_revision_id,
                    type=card.type,
                    effective_slots=effective_slots,
                )
            )

        # Validate composition
        signal_count = sum(1 for card in compiled_cards if card.role == "signal")
        exit_count = sum(1 for card in compiled_cards if card.role == "exit")

        if signal_count == 0:
            issues.append(
                Issue(
                    severity="error",
                    code="NO_SIGNALS",
                    message="Strategy has no signal cards attached",
                    path="attachments",
                )
            )

        if exit_count == 0:
            issues.append(
                Issue(
                    severity="warning",
                    code="NO_EXITS",
                    message="Strategy has no exit cards attached (positions may not close automatically)",
                    path="attachments",
                )
            )

        if exit_count > 1:
            issues.append(
                Issue(
                    severity="warning",
                    code="MULTIPLE_EXITS",
                    message=f"Strategy has {exit_count} exit cards (may cause conflicts)",
                    path="attachments",
                )
            )

        # Convert data requirements to list
        data_requirements: list[DataRequirement] = []
        # Timeframe to hours mapping (simplified)
        tf_to_hours = {
            "1m": 1 / 60,
            "5m": 5 / 60,
            "15m": 15 / 60,
            "1h": 1,
            "4h": 4,
            "1d": 24,
        }

        for (symbol, tf), min_bars in data_requirements_map.items():
            hours_per_bar = tf_to_hours.get(tf, 1)  # Default to 1 hour if unknown
            lookback_hours = min_bars * hours_per_bar
            data_requirements.append(
                DataRequirement(
                    symbol=symbol,
                    tf=tf,
                    min_bars=min_bars,
                    lookback_hours=lookback_hours,
                )
            )

        # Determine status
        error_count = sum(1 for issue in issues if issue.severity == "error")
        status_hint = "ready" if error_count == 0 else "fix_required"

        # Build compiled strategy (only if ready)
        compiled = None
        if status_hint == "ready":
            compiled = CompiledStrategy(
                strategy_id=strategy.id,
                universe=strategy.universe,
                cards=compiled_cards,
                data_requirements=data_requirements,
            )

        # Calculate validation summary
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        cards_validated = len(compiled_cards)

        return CompileStrategyResponse(
            status_hint=status_hint,
            compiled=compiled,
            issues=issues,
            validation_summary={
                "errors": error_count,
                "warnings": warning_count,
                "cards_validated": cards_validated,
            },
        )
