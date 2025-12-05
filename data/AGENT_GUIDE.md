# Agent Guide: Using Trading Strategy Archetypes

This guide explains how AI agents should use the different archetype types when creating trading strategies.

## Canonical Agent Workflow

The recommended workflow for creating a trading strategy is:

1. **Discover archetypes** - Browse `archetypes://{kind}` or `archetypes://all` resources to find available archetypes
2. **Choose one** - Select an archetype that matches the user's intent
3. **Get example slots** - Use `get_schema_example(type)` to get ready-to-use example slots
4. **Negotiate/modify slots** - Present key slots to the user in plain language, confirm or adjust, optionally validate with `validate_slots_draft`
5. **Create card** - Use `create_card(type, slots)` to create the card
6. **Create strategy** - Use `create_strategy(name, universe)` to create a new strategy
7. **Attach cards** - Use `attach_card(strategy_id, card_id, role, order)` to attach cards, or use `create_card` with `strategy_id` for auto-attachment
8. **Validate/compile** - Use `validate_strategy` or `compile_strategy` to check for issues
9. **Fix issues** - Address any issues reported, then re-compile
10. **Mark ready** - Once `compile_strategy` returns `status_hint='ready'`, optionally use `update_strategy_meta` to set `status='ready'`

Each tool's "Recommended workflow" section references this canonical workflow. Most strategies only need steps 1-5 (entries and exits). Gates and overlays are optional additions.

## Archetype Types Overview

There are **4 types of archetypes**, each serving a specific purpose in trading strategies:

### 1. **Entry** (formerly "signal")
**Purpose**: Define when to **open** a position.

**When to use**: Always required. Every strategy needs at least one entry archetype to generate trading signals.

**Examples**:
- `entry.trend_pullback` - Enter on pullbacks within a trend
- `entry.breakout_trendfollow` - Enter on breakouts in the direction of the trend
- `entry.xs_momentum` - Enter based on cross-sectional momentum ranking

**Workflow**:
1. Use `get_archetypes(kind="entry")` to see available entry archetypes
2. Use `get_schema_example(type_id)` to get example slot values
3. Create a card with `create_card(type=type_id, slots=...)`
4. Attach to strategy with `attach_card(strategy_id, card_id, role="entry")`

### 2. **Exit**
**Purpose**: Define when to **close** a position.

**When to use**: Highly recommended. Most strategies need at least one exit to manage risk and take profits.

**Examples**:
- `exit.take_profit_stop` - Exit at profit target or stop loss
- `exit.trailing_stop` - Exit when price reverses by a trailing amount
- `exit.time_stop` - Exit after a fixed time period
- `exit.squeeze_compression` - Exit when volatility compresses back into a squeeze

**Workflow**:
1. Use `get_archetypes(kind="exit")` to see available exit archetypes
2. Create exit cards similar to entry cards
3. Attach to strategy with `attach_card(strategy_id, card_id, role="exit")`
4. Multiple exits can be attached - they execute in order

**Important**: Exits are evaluated **after** entries. A strategy can have multiple exits (e.g., one for profit taking, one for stop loss).

### 3. **Gate**
**Purpose**: Conditionally **allow or block** other cards from executing.

**When to use**: Optional. Use gates to add conditional logic that filters when entries/exits can execute.

**Examples**:
- `gate.regime` - Only allow entries/exits when market regime matches criteria (trend, volatility, factors)
- `gate.event_risk_window` - Block entries/exits around high-risk events (earnings, FOMC, etc.)

**How gates work**:
- Gates have an `action.target_roles` field that specifies which cards they guard (e.g., `["entry"]`)
- Gates execute **before** the cards they guard
- If a gate blocks execution, the guarded cards don't execute
- Gates can guard multiple roles (e.g., both entries and exits)

**Workflow**:
1. Use `get_archetypes(kind="gate")` to see available gates
2. Create a gate card with `action.target_roles` set to the roles you want to guard
3. Attach to strategy with `attach_card(strategy_id, card_id, role="gate")`
4. Set the gate's `order` to be **lower** than the cards it guards (gates execute first)

**Example gate configuration**:
```json
{
  "context": { "symbol": "BTC-USD", "tf": "1h" },
  "event": {
    "regime": {
      "trend": "bullish",
      "volatility": "low"
    }
  },
  "action": {
    "target_roles": ["entry"],
    "mode": "allow"
  }
}
```

**Note**: Gates are less commonly used by agents. Most strategies work fine with just entries and exits. Only use gates when you need conditional filtering based on market regime or events.

### 4. **Overlay**
**Purpose**: **Modify** the risk/size of other cards.

**When to use**: Optional. Use overlays to scale position sizing or risk based on conditions.

**Examples**:
- `overlay.regime_scaler` - Scale position size based on market regime (e.g., reduce size in high volatility)

**How overlays work**:
- Overlays have an `action.target_roles` field that specifies which cards they modify (e.g., `["entry"]`)
- Overlays execute **after** the cards they modify
- Overlays scale the effective position size/risk
- Multiple overlays can stack (they multiply)

**Workflow**:
1. Use `get_archetypes(kind="overlay")` to see available overlays
2. Create an overlay card with `action.target_roles` set to the roles you want to modify
3. Attach to strategy with `attach_card(strategy_id, card_id, role="overlay")`
4. Set the overlay's `order` to be **higher** than the cards it modifies (overlays execute after)

**Example overlay configuration**:
```json
{
  "context": { "symbol": "BTC-USD", "tf": "1h" },
  "event": {
    "regime": {
      "volatility": "high"
    }
  },
  "action": {
    "target_roles": ["entry"],
    "scale_factor": 0.5
  }
}
```

**Note**: Overlays are less commonly used by agents. Most strategies work fine with fixed position sizing. Only use overlays when you need dynamic risk scaling.

## Complete Workflow Example

Here's a complete example of creating a strategy with all archetype types:

### Step 1: Create Entry Card
```python
# Get available entries
archetypes = get_archetypes(kind="entry")

# Get example slots for trend pullback entry
example = get_schema_example("entry.trend_pullback")

# Create entry card
entry_card = create_card(
    type="entry.trend_pullback",
    slots=example.slots  # Use example or modify as needed
)
```

### Step 2: Create Exit Card
```python
# Get example slots for take profit/stop loss exit
example = get_schema_example("exit.take_profit_stop")

# Create exit card
exit_card = create_card(
    type="exit.take_profit_stop",
    slots=example.slots
)
```

### Step 3: (Optional) Create Gate Card
```python
# Only if you need conditional filtering
example = get_schema_example("gate.regime")

# Modify to guard entries
slots = example.slots.copy()
slots["action"]["target_roles"] = ["entry"]

gate_card = create_card(
    type="gate.regime",
    slots=slots
)
```

### Step 4: Create Strategy
```python
strategy = create_strategy(
    name="Trend Pullback Strategy",
    universe=["BTC-USD", "ETH-USD"]
)
```

### Step 5: Attach Cards to Strategy
```python
# Attach gate first (order=1) - gates execute before entries
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=gate_card.card_id,
    role="gate",
    order=1
)

# Attach entry (order=2) - entries execute after gates
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=entry_card.card_id,
    role="entry",
    order=2
)

# Attach exit (order=3) - exits execute after entries
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=exit_card.card_id,
    role="exit",
    order=3
)
```

### Step 6: Compile and Validate
```python
# Compile strategy to check for issues
compiled = compile_strategy(strategy_id=strategy.strategy_id)

if compiled.status_hint == "ready":
    # Strategy is ready to run
    update_strategy_meta(strategy_id=strategy.strategy_id, status="ready")
else:
    # Fix issues shown in compiled.issues
    for issue in compiled.issues:
        print(f"{issue.severity}: {issue.message}")
```

## Execution Order

Cards execute in order based on their `order` field (lower numbers execute first):

1. **Gates** (order: 1-10) - Check conditions, allow/block downstream cards
2. **Entries** (order: 11-20) - Generate signals to open positions
3. **Exits** (order: 21-30) - Generate signals to close positions
4. **Overlays** (order: 31-40) - Modify position sizing/risk

**Best Practice**: Use order ranges to keep things organized:
- Gates: 1-10
- Entries: 11-20
- Exits: 21-30
- Overlays: 31-40

## Common Patterns

### Pattern 1: Simple Entry + Exit (Most Common)
- 1 entry card
- 1-2 exit cards (e.g., take profit + stop loss)
- No gates or overlays

### Pattern 2: Entry + Exit + Regime Gate
- 1 entry card
- 1-2 exit cards
- 1 gate card (regime filter)
- Gate guards entries (only enter in favorable regime)

### Pattern 3: Entry + Exit + Regime Overlay
- 1 entry card
- 1-2 exit cards
- 1 overlay card (scale size based on regime)
- Overlay modifies entries (reduce size in high volatility)

### Pattern 4: Multiple Entries + Multiple Exits
- 2+ entry cards (different entry conditions)
- 2+ exit cards (different exit conditions)
- All entries share the same exits

## Important Notes for Agents

1. **Always start with entries and exits** - These are the core of any strategy
2. **Gates are optional** - Only use when you need conditional filtering
3. **Overlays are optional** - Only use when you need dynamic risk scaling
4. **Check execution order** - Make sure gates execute before entries, overlays execute after
5. **Use `compile_strategy`** - Always compile before marking strategy as "ready"
6. **Read schema examples** - Use `get_schema_example` to get valid slot configurations
7. **Validate slots** - Use `validate_slots_draft` before creating cards to catch errors early

## Tool Reference

- `get_archetypes(kind=None)` - List all archetypes, optionally filtered by kind
- `get_archetype_schema(type_id)` - Get full schema for an archetype
- `get_schema_example(type_id)` - Get ready-to-use example slots
- `validate_slots_draft(type_id, slots)` - Validate slots before creating card
- `create_card(type, slots)` - Create a card from an archetype
- `create_strategy(name, universe)` - Create a new strategy
- `attach_card(strategy_id, card_id, role, order)` - Attach card to strategy
- `compile_strategy(strategy_id)` - Compile and validate strategy
- `validate_strategy(strategy_id)` - Check if strategy is ready to run

## Error Handling

All tools return structured errors with:
- `error_code`: Machine-readable error code
- `retryable`: Whether the error is retryable
- `recovery_hint`: Actionable guidance
- `details`: Additional context

Common error codes:
- `ARCHETYPE_NOT_FOUND`: Archetype doesn't exist - use `get_archetypes` to see available types
- `SCHEMA_VALIDATION_ERROR`: Slot values don't match schema - use `get_schema_example` for valid values
- `VALIDATION_ERROR`: Invalid parameter - check error message for details
- `NOT_FOUND`: Resource not found - check ID spelling

