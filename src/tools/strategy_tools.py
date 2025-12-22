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
# There are 4 roles that map directly to archetype kinds: entry, exit, gate, overlay
# Risk is controlled via overlays (dynamic scalers) and external run-time parameters.
# There is no separate 'risk' or 'sizing' card role.
VALID_ROLES = ["entry", "gate", "exit", "overlay"]
VALID_STATUSES = ["draft", "ready", "running", "paused", "stopped", "error"]


def _extract_and_compile_condition(effective_slots: dict[str, Any]) -> dict[str, Any] | None:
    """Extract and compile ConditionSpec from effective slots.

    Looks for ConditionSpec in:
    - event.condition (for entry.rule_trigger, exit.rule_trigger)
    - event.regime (for gate.regime, backwards compatible RegimeSpec)

    Returns compiled condition tree ready for runtime evaluation, or None if no condition found.
    """
    # Check event.condition (for rule_trigger archetypes)
    if "event" in effective_slots:
        event = effective_slots["event"]
        if "condition" in event:
            condition = event["condition"]
            # If it's a ConditionSpec (has "type" field), return as-is (already compiled)
            if isinstance(condition, dict) and "type" in condition:
                return condition
            # If it's a RegimeSpec (backwards compatible), wrap in ConditionSpec
            if isinstance(condition, dict) and "metric" in condition:
                return {"type": "regime", "regime": condition}

    # Check event.regime (for gate.regime)
    if "event" in effective_slots:
        event = effective_slots["event"]
        if "regime" in event:
            regime = event["regime"]
            # If it's a ConditionSpec (has "type" field), return as-is
            if isinstance(regime, dict) and "type" in regime:
                return regime
            # If it's a RegimeSpec (backwards compatible), wrap in ConditionSpec
            if isinstance(regime, dict) and "metric" in regime:
                return {"type": "regime", "regime": regime}

    return None


def _extract_execution_spec(effective_slots: dict[str, Any]) -> dict[str, Any] | None:
    """Extract ExecutionSpec from action.execution in effective slots.

    Returns ExecutionSpec dict if present, None otherwise.
    """
    if "action" in effective_slots:
        action = effective_slots["action"]
        if "execution" in action:
            return action["execution"]
    return None


def _extract_sizing_spec(effective_slots: dict[str, Any]) -> dict[str, Any] | None:
    """Extract SizingSpec from action.sizing in effective slots.

    Returns SizingSpec dict if present, None otherwise.
    """
    if "action" in effective_slots:
        action = effective_slots["action"]
        if "sizing" in action:
            return action["sizing"]
    return None


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
    """Response from add_card tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    attachments: list[dict[str, Any]] = Field(..., description="Updated attachments list")
    version: int = Field(..., description="Strategy version")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class DeleteCardResponse(BaseModel):
    """Response from delete_card tool."""

    strategy_id: str = Field(..., description="Strategy identifier")
    attachments: list[dict[str, Any]] = Field(..., description="Updated attachments list")
    version: int = Field(..., description="Strategy version")
    updated_at: str = Field(..., description="ISO8601 timestamp of last update")


class ListStrategiesResponse(BaseModel):
    """Response from list_strategies tool."""

    strategies: list[dict[str, Any]] = Field(..., description="List of strategies")
    count: int = Field(..., description="Total number of strategies")


class CompiledCard(BaseModel):
    """Compiled card with effective slots and compiled components."""

    role: str = Field(..., description="Card role")
    card_id: str = Field(..., description="Card identifier")
    card_revision_id: str | None = Field(None, description="Card revision identifier")
    type: str = Field(..., description="Archetype type")
    effective_slots: dict[str, Any] = Field(..., description="Merged slots (card + overrides)")
    compiled_condition: dict[str, Any] | None = Field(
        None, description="Compiled ConditionSpec tree for runtime evaluation (if condition exists)"
    )
    execution_spec: dict[str, Any] | None = Field(
        None, description="ExecutionSpec extracted from action (if present)"
    )
    sizing_spec: dict[str, Any] | None = Field(
        None, description="SizingSpec extracted from action (if present)"
    )


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
        thread_id: str | None = Field(None, description="Thread identifier that created this strategy"),
        universe: list[str] = Field(  # noqa: B008
            default_factory=list, description="Trading universe symbols"
        ),
    ) -> CreateStrategyResponse:
        """
        Create a new trading strategy.

        A strategy is a composition of cards (entries, exits, gates, overlays) with
        universe selection. Risk is controlled via overlays (dynamic scalers) and
        external run-time parameters. There is no separate 'risk' card role.

        Card roles (4 total, map directly to archetype kinds):
        - entry: Entry signals for opening positions (required - at least one)
        - exit: Exit rules for closing positions (recommended - at least one)
        - gate: Conditional filters that allow/block other cards (optional)
        - overlay: Risk/size modifiers that scale position sizing dynamically (optional)

        **Agent behavior:**
        - Ask user if they want multiple entries, multiple exits, or regime filters.
        - If they don't care, default to minimal: 1 entry + 1 exit, no gate/overlay.

        Recommended workflow (see "Canonical agent workflow" in AGENT_GUIDE.md):
        1. Create strategy with create_strategy
        2. Add cards to strategy using add_card (start with entries and exits)
        3. Use compile_strategy to validate before marking as ready

        Args:
            name: Strategy name
            owner_id: Owner identifier (optional)
            thread_id: Thread identifier that created this strategy (optional)
            universe: List of trading symbols (e.g., ['BTC-USD']). If omitted, the strategy
                will be created with an empty universe and will not be runnable until a universe
                is set via update_strategy_meta or another tool. Most strategies should have at
                least one symbol before compilation.

        Returns:
            CreateStrategyResponse with generated strategy_id and initial configuration
        """
        # Create strategy
        strategy = Strategy(
            id="",  # Will be generated by Firestore
            owner_id=owner_id,
            thread_id=thread_id,
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
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found

        Error Handling:
            Errors include structured information with error_code,
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

        **Agent behavior:**
        - Only set `status='ready'` after successful `compile_strategy` with `status_hint='ready'`.
        - Do not set `running`, `paused`, or `stopped` unless explicitly instructed by the user.

        Args:
            strategy_id: Strategy identifier
            name: Strategy name (optional)
            status: Strategy status: draft, ready, running, paused, stopped, error (optional)
            universe: Trading universe symbols (optional)

        Returns:
            UpdateStrategyMetaResponse with updated strategy data

        Raises:
            StructuredToolError: With error codes:
                - STRATEGY_NOT_FOUND: If strategy not found
                - INVALID_STATUS: If status is invalid
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
    def add_card(
        strategy_id: str = Field(..., description="Strategy identifier (required)"),
        type: str = Field(..., description="Archetype identifier (e.g., 'entry.trend_pullback')"),
        slots: dict[str, Any] = Field(..., description="Slot values to validate and store"),  # noqa: B008
        role: str | None = Field(
            None,
            description="Optional card role (entry, gate, exit, overlay). If not provided, role will be automatically determined from the archetype type (e.g., 'entry.trend_pullback' → 'entry').",
        ),
        overrides: dict[str, Any] = Field(  # noqa: B008
            default_factory=dict, description="Optional slot value overrides for attachment"
        ),
        follow_latest: bool = Field(
            default=False,
            description="If true, use latest card version; if false, pin current version",
        ),
        enabled: bool = Field(default=True, description="Whether attachment is enabled"),
    ) -> AttachCardResponse:
        """
        Add a card to a strategy (creates the card and automatically attaches it).

        This is the primary way to create and add cards to a strategy. It creates a new card
        and automatically attaches it to the specified strategy. The role is automatically
        determined from the archetype type if not provided.

        Cards are added with a **role** (entry, gate, exit, overlay) that determines execution order:
        - gate: Conditional filters, execute **first** and can block entries/exits.
        - entry: Entry signals, execute **after gates**, open positions.
        - exit: Exit rules, execute **after entries**, close/reduce positions.
        - overlay: Risk/size modifiers, execute **last**, scale position size.

        Execution order is automatically determined by role - you don't need to specify it.

        Recommended workflow (see "Canonical agent workflow" in AGENT_GUIDE.md):
        1. Create strategy using create_strategy
        2. Add cards to strategy using add_card (start with entries and exits)
        3. Use compile_strategy to validate before marking as ready

        Args:
            strategy_id: Strategy identifier (required - card will be automatically attached to this strategy)
            type: Archetype identifier (e.g., 'entry.trend_pullback', 'exit.take_profit_stop', 'gate.regime', 'overlay.regime_scaler')
            slots: Slot values to validate and store. Must match the archetype's JSON schema.
            role: Optional card role (entry, gate, exit, overlay). If not provided, role will be
                automatically determined from the archetype type (first part before the dot).
            overrides: Optional slot value overrides for attachment.
                Overrides use deep merge: nested objects are merged recursively,
                not replaced. For example, if card has {"context": {"symbol": "BTC-USD", "tf": "1h"}}
                and you provide {"context": {"tf": "4h"}}, the result is
                {"context": {"symbol": "BTC-USD", "tf": "4h"}} (tf is updated, symbol is preserved).
                To replace an entire nested object, you must provide all its fields.
            follow_latest: If true, use latest card version; if false, pin current version.
                Use `follow_latest = true` when user expects ongoing improvements to propagate;
                use `false` when they want a stable, reproducible configuration for backtests or production runs.
            enabled: Whether attachment is enabled (default: true)

        Returns:
            AttachCardResponse with updated attachments list and card_id

        Raises:
            StructuredToolError: With error codes:
                - ARCHETYPE_NOT_FOUND: If archetype schema not found
                - SCHEMA_VALIDATION_ERROR: If slot validation fails
                - INVALID_ROLE: If role is invalid
                - STRATEGY_NOT_FOUND: If strategy not found
                - DUPLICATE_ATTACHMENT: If card is already attached

        Error Handling:
            All errors include structured information with error_code,
            recovery_hint, and details for agentic decision-making.
        """
        # Import card creation logic (avoid circular import)
        from src.tools.card_tools import _validate_slots_against_schema

        # Get strategy first to validate it exists
        strategy = strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise not_found_error(
                resource_type="Strategy",
                resource_id=strategy_id,
                recovery_hint="Use list_strategies to see all available strategies.",
            )

        # Fetch schema for validation
        schema = schema_repo.get_by_type_id(type)
        if schema is None:
            raise not_found_error(
                resource_type="Archetype",
                resource_id=type,
                recovery_hint="Browse archetypes://all resource to see available archetypes.",
            )

        # Validate slots against JSON schema
        validation_errors = _validate_slots_against_schema(slots, schema.json_schema, schema_repo)
        if validation_errors:
            from src.tools.errors import schema_validation_error

            raise schema_validation_error(
                type_id=type,
                errors=validation_errors,
                recovery_hint=f"Browse archetype-schemas://{type.split('.', 1)[0]} resource to see valid values, constraints, and examples.",
            )

        # Determine role from type if not provided
        if role is None:
            # Extract role from type (first part before dot)
            # e.g., 'entry.trend_pullback' -> 'entry', 'exit.take_profit_stop' -> 'exit'
            role = type.split(".", 1)[0] if "." in type else type

        # Validate role
        if role not in VALID_ROLES:
            raise StructuredToolError(
                message=f"Invalid role: {role}. Must be one of: {VALID_ROLES}. Role was inferred from type '{type}'. Provide an explicit role if the type doesn't match a valid role.",
                error_code=ErrorCode.INVALID_ROLE,
                recovery_hint=f"Use one of: {', '.join(VALID_ROLES)}. Provide an explicit role parameter if the archetype type doesn't start with a valid role.",
                details={
                    "provided_role": role,
                    "valid_roles": VALID_ROLES,
                    "inferred_from_type": type,
                },
            )

        # Always use current schema etag - this is internal to MCP
        schema_etag = schema.etag

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

        # Check if card is already attached (shouldn't happen for new card, but check anyway)
        for att in strategy.attachments:
            if att.card_id == created_card.id:
                raise validation_error(
                    message=f"Card {created_card.id} is already attached to strategy {strategy_id}.",
                    recovery_hint="Use delete_card first to remove it, or update the attachment manually.",
                    details={"card_id": created_card.id, "strategy_id": strategy_id},
                )

        # Determine card_revision_id (use updated_at as simple revision identifier for MVP)
        card_revision_id = None
        if not follow_latest:
            card_revision_id = created_card.updated_at  # Simple revision ID for MVP

        # Create attachment
        attachment = Attachment(
            card_id=created_card.id,
            role=role,
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
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found
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

            # Extract and compile ConditionSpec, ExecutionSpec, SizingSpec
            compiled_condition = _extract_and_compile_condition(effective_slots)
            execution_spec = _extract_execution_spec(effective_slots)
            sizing_spec = _extract_sizing_spec(effective_slots)

            # Create compiled card (for validation summary)
            compiled_cards.append(
                CompiledCard(
                    role=attachment.role,
                    card_id=attachment.card_id,
                    card_revision_id=card_revision_id,
                    type=card.type,
                    effective_slots=effective_slots,
                    compiled_condition=compiled_condition,
                    execution_spec=execution_spec,
                    sizing_spec=sizing_spec,
                )
            )

        # Validate composition
        entry_count = sum(1 for card in compiled_cards if card.role == "entry")
        exit_count = sum(1 for card in compiled_cards if card.role == "exit")

        if entry_count == 0:
            issues.append(
                Issue(
                    severity="error",
                    code="NO_ENTRIES",
                    message="Strategy has no entry cards attached",
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

        # MVP: Single-asset trading guarantee
        traded_symbols = set()
        for card in compiled_cards:
            if card.role == "entry":
                effective_slots = card.effective_slots
                symbol = None

                # Get symbol from context
                if "context" in effective_slots:
                    context = effective_slots["context"]
                    symbol = context.get("symbol")

                # For entry.intermarket_trigger, verify context.symbol == follower_symbol
                if card.type == "entry.intermarket_trigger":
                    if "event" in effective_slots:
                        event = effective_slots["event"]
                        if "lead_follow" in event:
                            lead_follow = event["lead_follow"]
                            follower_symbol = lead_follow.get("follower_symbol")
                            if symbol != follower_symbol:
                                issues.append(
                                    Issue(
                                        severity="error",
                                        code="MVP_SINGLE_ASSET_VIOLATION",
                                        message=f"entry.intermarket_trigger requires context.symbol ({symbol}) to equal event.lead_follow.follower_symbol ({follower_symbol}). Leader symbols are observation-only.",
                                        path=f"attachments[{card.card_id}].effective_slots",
                                    )
                                )
                            symbol = follower_symbol  # Use follower_symbol as the traded symbol

                if symbol:
                    traded_symbols.add(symbol)

        # Verify single traded asset
        if len(traded_symbols) > 1:
            issues.append(
                Issue(
                    severity="error",
                    code="MVP_MULTIPLE_ASSETS",
                    message=f"MVP constraint violation: Strategy trades multiple assets {sorted(traded_symbols)}. MVP requires single-asset trading. Use entry.intermarket_trigger for observation-only triggers from other symbols.",
                    path="attachments",
                )
            )
        elif len(traded_symbols) == 1:
            traded_symbol = list(traded_symbols)[0]
            # Verify strategy universe matches (if set)
            if strategy.universe and len(strategy.universe) > 1:
                issues.append(
                    Issue(
                        severity="error",
                        code="MVP_UNIVERSE_MISMATCH",
                        message=f"Strategy universe {strategy.universe} contains multiple symbols, but only {traded_symbol} is traded. MVP requires single-asset strategies.",
                        path="universe",
                    )
                )
            elif strategy.universe and traded_symbol not in strategy.universe:
                issues.append(
                    Issue(
                        severity="error",
                        code="MVP_UNIVERSE_MISMATCH",
                        message=f"Traded symbol {traded_symbol} not in strategy universe {strategy.universe}",
                        path="universe",
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

        If universe is empty, compile_strategy will return `status_hint='fix_required'` and
        an issue explaining that no symbols are configured.

        **Agent behavior:**
        - After compile_strategy with `status_hint != 'ready'`, explain issues and propose
          one concrete fix at a time (rather than changing many things silently).
        - Ask user if they want multiple entries, multiple exits, or regime filters.
        - If they don't care, default to minimal: 1 entry + 1 exit, no gate/overlay.

        Recommended workflow:
        1. Create strategy using create_strategy
        2. Add cards to strategy using add_card
        3. Compile strategy using compile_strategy to validate and get data requirements
        4. Fix any issues reported
        5. Re-compile until status_hint is "ready"

        Args:
            strategy_id: Strategy identifier

        Returns:
            CompileStrategyResponse with status_hint, compiled plan, and issues

        Raises:
            StructuredToolError: With error code STRATEGY_NOT_FOUND if strategy not found

        Error Handling:
            Errors include structured information with error_code,
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

            # Extract and compile ConditionSpec, ExecutionSpec, SizingSpec
            compiled_condition = _extract_and_compile_condition(effective_slots)
            execution_spec = _extract_execution_spec(effective_slots)
            sizing_spec = _extract_sizing_spec(effective_slots)

            # Create compiled card
            compiled_cards.append(
                CompiledCard(
                    role=attachment.role,
                    card_id=attachment.card_id,
                    card_revision_id=card_revision_id,
                    type=card.type,
                    effective_slots=effective_slots,
                    compiled_condition=compiled_condition,
                    execution_spec=execution_spec,
                    sizing_spec=sizing_spec,
                )
            )

        # Validate universe
        if not strategy.universe:
            issues.append(
                Issue(
                    severity="error",
                    code="EMPTY_UNIVERSE",
                    message="Strategy has no symbols in universe. Set universe via update_strategy_meta before compilation.",
                    path="universe",
                )
            )

        # Validate composition
        entry_count = sum(1 for card in compiled_cards if card.role == "entry")
        exit_count = sum(1 for card in compiled_cards if card.role == "exit")

        if entry_count == 0:
            issues.append(
                Issue(
                    severity="error",
                    code="NO_ENTRIES",
                    message="Strategy has no entry cards attached",
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

        # MVP: Single-asset trading guarantee
        traded_symbols = set()
        for card in compiled_cards:
            if card.role == "entry":
                effective_slots = card.effective_slots
                symbol = None

                # Get symbol from context
                if "context" in effective_slots:
                    context = effective_slots["context"]
                    symbol = context.get("symbol")

                # For entry.intermarket_trigger, verify context.symbol == follower_symbol
                if card.type == "entry.intermarket_trigger":
                    if "event" in effective_slots:
                        event = effective_slots["event"]
                        if "lead_follow" in event:
                            lead_follow = event["lead_follow"]
                            follower_symbol = lead_follow.get("follower_symbol")
                            if symbol != follower_symbol:
                                issues.append(
                                    Issue(
                                        severity="error",
                                        code="MVP_SINGLE_ASSET_VIOLATION",
                                        message=f"entry.intermarket_trigger requires context.symbol ({symbol}) to equal event.lead_follow.follower_symbol ({follower_symbol}). Leader symbols are observation-only.",
                                        path=f"attachments[{card.card_id}].effective_slots",
                                    )
                                )
                            symbol = follower_symbol  # Use follower_symbol as the traded symbol

                if symbol:
                    traded_symbols.add(symbol)

        # Verify single traded asset
        if len(traded_symbols) > 1:
            issues.append(
                Issue(
                    severity="error",
                    code="MVP_MULTIPLE_ASSETS",
                    message=f"MVP constraint violation: Strategy trades multiple assets {sorted(traded_symbols)}. MVP requires single-asset trading. Use entry.intermarket_trigger for observation-only triggers from other symbols.",
                    path="attachments",
                )
            )
        elif len(traded_symbols) == 1:
            traded_symbol = list(traded_symbols)[0]
            # Verify strategy universe matches (if set)
            if strategy.universe and len(strategy.universe) > 1:
                issues.append(
                    Issue(
                        severity="error",
                        code="MVP_UNIVERSE_MISMATCH",
                        message=f"Strategy universe {strategy.universe} contains multiple symbols, but only {traded_symbol} is traded. MVP requires single-asset strategies.",
                        path="universe",
                    )
                )
            elif strategy.universe and traded_symbol not in strategy.universe:
                issues.append(
                    Issue(
                        severity="error",
                        code="MVP_UNIVERSE_MISMATCH",
                        message=f"Traded symbol {traded_symbol} not in strategy universe {strategy.universe}",
                        path="universe",
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
