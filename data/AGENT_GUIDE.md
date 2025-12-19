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
7. **Attach cards** - Use `attach_card(strategy_id, card_id, role)` to attach cards. Execution order is automatically determined by role.
8. **Validate/compile** - Use `validate_strategy` or `compile_strategy` to check for issues
9. **Fix issues** - Address any issues reported, then re-compile
10. **Mark ready** - Once `compile_strategy` returns `status_hint='ready'`, optionally use `update_strategy_meta` to set `status='ready'`

Each tool's "Recommended workflow" section references this canonical workflow. Most strategies only need steps 1-5 (entries and exits). Gates and overlays are optional additions.

## Where does risk live?

**Entries define signals and direction. Exits and overlays define most risk. Entries can optionally carry a `risk` override.**

**Rule**: All archetypes (entry and exit) use `PositionRiskSpec` at the top level (`risk` field), NOT under `event`.

- **Entry cards**: Define when to open a position and in which direction. Entry cards can optionally include a `risk` block (shared `PositionRiskSpec`) at the top level to override default risk settings (e.g., wider stops for breakouts), but this is not required.
- **Exit cards**: Define when to close positions. Some exit archetypes **require** a `risk` block because they encode numeric thresholds (e.g. `exit.trailing_stop`); others (like band/structure exits) can work structurally with or without explicit `risk`. All exit cards use `PositionRiskSpec` at the top level.
- **Overlay cards**: Modify position sizing/risk dynamically based on conditions (e.g., reduce size in high volatility) using the same shared `risk` spec where applicable.

By default, risk (stops, take profits, time stops) is configured in exit cards. Entry cards can optionally override risk parameters, but they don't have to – you can keep entries "signal-only". Overlays scale or modulate whatever risk the base entries/exits already define.

**Consistency Rule**: 
- Entry archetypes → `risk: PositionRiskSpec` (top level, optional)
- Exit archetypes → `risk: PositionRiskSpec` (top level, required for some exits)
- Risk MUST be at top level, NOT under `event`

## Archetype Types Overview

There are **4 types of archetypes**, each serving a specific purpose in trading strategies:

### 1. **Entry** (formerly "signal")
**Purpose**: Define when to **open** a position.

**When to use**: Always required. Every strategy needs at least one entry archetype to generate trading signals.

**Examples**:
- `entry.trend_pullback` - Enter on pullbacks within a trend
- `entry.breakout_trendfollow` - Enter on breakouts in the direction of the trend
- `entry.rule_trigger` - Enter based on a ConditionSpec condition (e.g., "buy if ret_pct <= 1%")

**Workflow**:
1. Use `get_archetypes(kind="entry")` to see available entry archetypes
2. Use `get_schema_example(type_id)` to get example slot values
3. Create a card with `create_card(type=type_id, slots=...)`
4. Attach to strategy with `attach_card(strategy_id, card_id, role="entry")`

### 2. **Exit**
**Purpose**: Define when to **close** a position.

**When to use**: Highly recommended. Most strategies need at least one exit to manage risk and take profits.

**Examples**:
- `exit.trailing_stop` - Exit when price reverses by a trailing amount
- `exit.squeeze_compression` - Exit when volatility compresses back into a squeeze
- `exit.rule_trigger` - Exit based on a ConditionSpec condition (e.g., "exit if ret_pct > 5%" for take profit/stop loss, or time-based exits)

**Workflow**:
1. Use `get_archetypes(kind="exit")` to see available exit archetypes
2. Create exit cards similar to entry cards
3. Attach to strategy with `attach_card(strategy_id, card_id, role="exit")`
4. Multiple exits can be attached - they execute in order

**Important**: Exits are evaluated **after** entries. A strategy can have multiple exits (e.g., one for profit taking, one for stop loss).

### 3. **Gate**
**Purpose**: Conditionally **allow or block** other cards from executing.

**When to use**: Optional. Use gates to add conditional logic that filters when entries/exits can execute.

**Role boundary**: **Entries encode trading ideas/conditions; gates only control when those cards are allowed to act (time, events, high-level regimes).** Do not put trade logic (e.g., "buy if ret_pct <= 1%") into gates. Use entry cards (like `entry.rule_trigger`) for trading conditions instead.

**Examples**:
- `gate.regime` - Only allow entries/exits when market regime matches criteria (trend, volatility, factors)
- `gate.event_risk_window` - Block entries/exits around high-risk events (earnings, FOMC, etc.)

**How gates work**:
- Gates have an `action.target_roles` field that specifies which cards they guard (e.g., `["entry"]`). Valid target roles are the same 4 strategy roles: `entry`, `exit`, `gate`, `overlay`.
- Gates execute **before** the cards they guard
- If a gate blocks execution, the guarded cards don't execute
- Gates can guard multiple roles (e.g., both entries and exits)

**Workflow**:
1. Use `get_archetypes(kind="gate")` to see available gates
2. Create a gate card with `action.target_roles` set to the roles you want to guard
3. Attach to strategy with `attach_card(strategy_id, card_id, role="gate")`
4. Gates automatically execute before the cards they guard (execution order is determined by role)

**Example gate configuration**:
```json
{
  "context": { "symbol": "BTC-USD", "tf": "1h" },
  "event": {
    "regime": {
      "type": "regime",
      "regime": {
        "metric": "trend_regime",
        "tf": "1h",
        "op": "==",
        "value": "up",
        "ma_fast": 20,
        "ma_slow": 50
      }
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
- Overlays have an `action.target_roles` field that specifies which cards they modify (e.g., `["entry"]`). Valid target roles are the same 4 strategy roles: `entry`, `exit`, `gate`, `overlay`.
- Overlays execute **after** the cards they modify
- Overlays scale the effective position size/risk
- Multiple overlays can stack (they multiply)

**Workflow**:
1. Use `get_archetypes(kind="overlay")` to see available overlays
2. Create an overlay card with `action.target_roles` set to the roles you want to modify
3. Attach to strategy with `attach_card(strategy_id, card_id, role="overlay")`
4. Overlays automatically execute after the cards they modify (execution order is determined by role)

**Example overlay configuration**:
```json
{
  "context": { "symbol": "BTC-USD", "tf": "1h" },
  "event": {
    "regime": {
      "type": "regime",
      "regime": {
        "metric": "vol_regime",
        "tf": "1h",
        "op": "==",
        "value": "high",
        "lookback_bars": 200
      }
    }
  },
  "action": {
    "target_roles": ["entry"],
    "scale_risk_frac": 0.5,
    "scale_size_frac": 0.5
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
# Get example slots for rule-based exit (take profit/stop loss)
example = get_schema_example("exit.rule_trigger")

# Create exit card
exit_card = create_card(
    type="exit.rule_trigger",
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
# Attach gate - gates automatically execute before entries
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=gate_card.card_id,
    role="gate"
)

# Attach entry - entries automatically execute after gates
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=entry_card.card_id,
    role="entry"
)

# Attach exit - exits automatically execute after entries
attach_card(
    strategy_id=strategy.strategy_id,
    card_id=exit_card.card_id,
    role="exit"
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

Cards execute in a fixed order based on their role (you don't need to specify this):

1. **Gates** - Check conditions, allow/block downstream cards (execute first)
2. **Entries** - Generate signals to open positions (execute after gates)
3. **Exits** - Generate signals to close positions (execute after entries)
4. **Overlays** - Modify position sizing/risk (execute last)

Execution order is automatically determined by role - gates always execute before entries/exits, and overlays always execute after the cards they modify.

## Context patterns

Different archetypes use `context` in slightly different ways. As an agent, you should not assume that every card has both `tf` and `symbol` in context:

- **Per-symbol / timeframe context** (most chart-based entries and exits)
  - Shape: `{"tf": "...", "symbol": "..."}`.
  - Used by archetypes like `entry.trend_pullback`, `entry.range_mean_reversion`, `entry.breakout_trendfollow`, `exit.trailing_stop`, `exit.rule_trigger`, etc.
- **Portfolio / cross-sectional context**
  - Shape: `{}` (empty object, no `tf` or `symbol`).
  - Timeframe and universe live inside the event block (not used in MVP - single asset strategies only).
- **Event- or session-driven context**
  - Shape: typically `{ "symbol": "..." }` (no `tf`), with timing derived from events or sessions (`entry.event_followthrough`, `entry.gap_play`).

Always check the archetype schema for the expected context shape and explain that shape back to the user in plain language.

## BandSpec / RiskSpec quick reference

Many archetypes share common band and risk specs via `BandSpec` and `PositionRiskSpec`:

- **BandSpec (lookback in bars, not days)**:
  - `length` is in **bars**; effective horizon is `tf × length`.
  - Handy conversions:
    - 1h timeframe: 1 day ≈ 24 bars, 30 days ≈ 720 bars, 150 days ≈ 3600 bars.
    - 15m timeframe: 1 day ≈ 96 bars, 30 days ≈ 2880 bars.
  - When a user says “N days lookback”, convert to bars based on the chosen timeframe.
- **PositionRiskSpec (shared risk spec)**:
  - **Note**: This risk block is shared between entries and exits. Fields like `tp_pct`, `sl_pct`, `sl_atr`, `tp_rr`, and `time_stop_bars` can be used in both entry and exit cards regardless of card kind. Exit-only behavior (close/reduce/reverse) is specified in `ExitActionSpec`, not in the risk spec.
  - Percentage stops/targets: `tp_pct`, `sl_pct` (e.g. 5 = +5%, 2 = -2%).
  - ATR-based stops: `sl_atr` (e.g. 1.5–2.0 for normal, 2.5–3.0 for wider).
  - Risk–reward TP: `tp_rr` (e.g. 2.0 = TP at 2× stop distance).
  - Time stops: `time_stop_bars` is in **bars**; effective duration is `tf × time_stop_bars` (e.g. 24 bars on 1h ≈ 1 day).

## ConditionSpec and RegimeSpec metrics

**ConditionSpec = composable boolean condition language.** All boolean logic in triggers and gates uses ConditionSpec. For single conditions, use ConditionSpec with `type='regime'` and a RegimeSpec object.

**RegimeSpec = atomic condition on a metric (trend, volatility, return, gap, VWAP, session).** RegimeSpec is used as a leaf node inside ConditionSpec (via `ConditionSpec(type='regime', regime=RegimeSpec)`). It's not just for "regimes" - it's the shared primitive layer for expressing any condition on market metrics.

RegimeSpec supports built-in metrics for trend, volatility, return, gap, VWAP distance, and derived regime classifications. These metrics are used in gates, overlays, and the `entry.rule_trigger` / `exit.rule_trigger` archetypes via ConditionSpec:

- **Trend metrics**:
  - `trend_ma_relation` - Fast MA vs slow MA spread (positive = uptrend). Requires `ma_fast` and `ma_slow`.
  - `trend_adx` - Average Directional Index (>25 = strong trend)
  - `trend_regime` - Derived classification: 'up', 'down', 'range' (uses `==` or `!=` operators with string values)

- **Volatility metrics**:
  - `vol_bb_width_pctile` - Percentile rank of Bollinger Band width vs lookback
  - `vol_atr_pct` - ATR as percentage of price
  - `vol_regime` - Derived classification: 'quiet', 'normal', 'high' (uses `==` or `!=` operators with string values)

- **Return metrics**:
  - `ret_pct` - N-bar percentage return (controlled by `lookback_bars`). Example: `lookback_bars=1` for 1-bar return, `lookback_bars=24` for 24-bar return on 1h timeframe ≈ 1 day.

- **Gap metrics**:
  - `gap_pct` - Percentage gap from prior close. Requires `session` (us/eu/asia).

- **VWAP metrics**:
  - `dist_from_vwap_pct` - Distance from anchored VWAP as percentage. Requires `vwap_anchor` (VWAPAnchorSpec).

- **Session metrics**:
  - `session_phase` - Session window classification: 'open', 'close', 'overnight'. Requires `session` (us/eu/asia). Uses `==` or `!=` operators with string values.

- **Risk metrics**:
  - `risk_event_prob` - Probability of risk events

Use these built-in metrics for all regime conditions. For simple return-based conditions like "day not up more than 1%", use ConditionSpec with `type='regime'` and a RegimeSpec using `ret_pct` with appropriate `lookback_bars`. For simple rule-based entries, use `entry.rule_trigger` with ConditionSpec wrapping any of these metrics.

## Architecture: Primitives vs Archetypes

The system is built on two layers:

### Rule Layer (Primitives)
Shared building blocks defined in `common_defs.json`:
- **Return metrics**: `ret_pct` (via RegimeSpec, wrapped in ConditionSpec)
- **Volatility metrics**: `vol_bb_width_pctile`, `vol_atr_pct`, `vol_regime` (via RegimeSpec, wrapped in ConditionSpec)
- **Gap metrics**: `gap_pct` (via RegimeSpec, wrapped in ConditionSpec)
- **VWAP metrics**: `dist_from_vwap_pct` (via RegimeSpec, wrapped in ConditionSpec)
- **Session metrics**: `session_phase` (via RegimeSpec, wrapped in ConditionSpec)
- **Band relationships**: `BandSpec`, `BandEvent`
- **Breakouts/levels**: `BreakoutSpec`, `RetestSpec`
- **Distance to anchors**: `VWAPAnchorSpec`
- **Session boundaries**: `SessionSpec`
- **Trend conditions**: `MASpec`, `trend_adx`, `trend_regime` (via RegimeSpec, wrapped in ConditionSpec)
- **Confirmations**: `Confirm`

These are the "atoms" - reusable conditions that any archetype can use.

### Idea Layer (Archetypes)
Patterns built from primitives:
- `entry.trend_pullback` = uptrend (`MASpec`) + pullback (`BandEvent` + `BandSpec`) + confirm
- `entry.squeeze_expansion` = vol compression (`SqueezeSpec`) + breakout
- `entry.breakout_retest` = breakout (`BreakoutSpec`) + pullback depth (`RetestSpec`)
- `entry.rule_trigger` = ConditionSpec (use `type='regime'` for single conditions) + action (escape hatch for simple entry cases)
- `exit.rule_trigger` = ConditionSpec (use `type='regime'` for single conditions) + action (escape hatch for simple exit cases)

These are the "molecules" - semantic patterns that express trading ideas.

### Why This Matters
- **Primitives** give you flexibility to express any condition
- **Archetypes** give you semantic compression and discoverability
- **Rule-trigger archetype** gives you an escape hatch when you just need "if X then Y"

Use archetypes when they match the user's intent. Use `entry.rule_trigger` or `exit.rule_trigger` when the user expresses a simple single-condition rule. Use gates for environment filtering, not trade logic.

## Full Strategy Document Example

Here's a complete strategy document showing how cards are composed with target roles/ids:

```json
{
  "id": "strategy_123",
  "name": "Trend Pullback with Regime Filter",
  "universe": ["BTC-USD", "ETH-USD"],
  "status": "ready",
  "attachments": [
    {
      "card_id": "gate_card_1",
      "role": "gate",
      "enabled": true,
      "follow_latest": false
    },
    {
      "card_id": "entry_card_1",
      "role": "entry",
      "enabled": true,
      "follow_latest": false
    },
    {
      "card_id": "exit_card_1",
      "role": "exit",
      "enabled": true,
      "follow_latest": false
    },
    {
      "card_id": "exit_card_2",
      "role": "exit",
      "enabled": true,
      "follow_latest": false
    },
    {
      "card_id": "overlay_card_1",
      "role": "overlay",
      "enabled": true,
      "follow_latest": false
    }
  ]
}
```

**Gate card** (`gate_card_1`):
```json
{
  "type": "gate.regime",
  "slots": {
    "context": { "tf": "1h", "symbol": "BTC-USD" },
    "event": {
      "regime": {
        "type": "regime",
        "regime": {
          "metric": "trend_ma_relation",
          "tf": "1h",
          "op": ">",
          "value": 0.0,
          "ma_fast": 20,
          "ma_slow": 50
        }
      }
    },
    "action": {
      "mode": "allow",
      "target_roles": ["entry"]
    }
  }
}
```

**Entry card** (`entry_card_1`):
```json
{
  "type": "entry.trend_pullback",
  "slots": {
    "context": { "tf": "1h", "symbol": "BTC-USD" },
    "event": {
      "dip": {
        "kind": "distance",
        "mode": "band_mult",
        "side": "away_lower",
        "thresh": 1.5
      },
      "dip_band": {
        "band": "bollinger",
        "length": 24,
        "mult": 2.0
      },
      "trend_gate": {
        "fast": 20,
        "slow": 50,
        "op": ">"
      }
    },
    "action": {
      "direction": "long",
      "confirm": "close_confirm"
    }
  }
}
```

**Exit card 1** (`exit_card_1` - Take Profit):
```json
{
  "type": "exit.rule_trigger",
  "slots": {
    "context": { "tf": "1h", "symbol": "BTC-USD" },
    "event": {
      "condition": {
        "type": "regime",
        "regime": {
          "metric": "ret_pct",
          "tf": "1h",
          "op": ">=",
          "value": 4.0,
          "lookback_bars": 1
        }
      }
    },
    "action": {
      "mode": "close"
    },
    "risk": {
      "tp_rr": 2.0
    }
  }
}
```

**Exit card 2** (`exit_card_2` - Stop Loss):
```json
{
  "type": "exit.rule_trigger",
  "slots": {
    "context": { "tf": "1h", "symbol": "BTC-USD" },
    "event": {
      "condition": {
        "type": "regime",
        "regime": {
          "metric": "ret_pct",
          "tf": "1h",
          "op": "<=",
          "value": -3.0,
          "lookback_bars": 1
        }
      }
    },
    "action": {
      "mode": "close"
    },
    "risk": {
      "sl_atr": 1.5
    }
  }
}
```

**Overlay card** (`overlay_card_1`):
```json
{
  "type": "overlay.regime_scaler",
  "slots": {
    "context": { "tf": "1h", "symbol": "BTC-USD" },
    "event": {
      "regime": {
        "type": "regime",
        "regime": {
          "metric": "vol_bb_width_pctile",
          "tf": "1h",
          "op": ">",
          "value": 80,
          "lookback_bars": 200
        }
      }
    },
    "action": {
      "target_roles": ["entry"],
      "scale_risk_frac": 0.5,
      "scale_size_frac": 0.5
    }
  }
}
```

**Composition notes**:
- The gate (`gate_card_1`) guards entries via `action.target_roles: ["entry"]`
- The entry (`entry_card_1`) defines the signal (trend pullback)
- Exit 1 (`exit_card_1`) takes profit at 2R (risk-reward ratio)
- Exit 2 (`exit_card_2`) stops loss at 1.5 ATR
- The overlay (`overlay_card_1`) reduces position size by 50% when volatility is high, targeting entries via `action.target_roles: ["entry"]`

Execution order is automatic: gate → entry → exits → overlay.

## Composite Example: BTC Sunday Strategy

A common pattern is combining a time filter gate with a rule-based entry. For example, "BTC Sunday: buy if day not up more than 1%":

**Gate card** (`gate.time_filter`):
```json
{
  "type": "gate.time_filter",
  "slots": {
    "context": { "tf": "1d", "symbol": "BTC-USD" },
    "event": {
      "time_filter": {
        "days_of_week": ["sunday"],
        "timezone": "UTC"
      }
    },
    "action": {
      "mode": "allow",
      "target_roles": ["entry"]
    }
  }
}
```

**Entry card** (`entry.rule_trigger`):
```json
{
  "type": "entry.rule_trigger",
  "slots": {
    "context": { "tf": "1d", "symbol": "BTC-USD" },
    "event": {
      "condition": {
        "type": "regime",
        "regime": {
          "metric": "ret_pct",
          "tf": "1d",
          "op": "<=",
          "value": 1.0,
          "lookback_bars": 1
        }
      }
    },
    "action": {
      "direction": "long",
      "confirm": "none"
    },
    "risk": {
      "sl_pct": 2.0,
      "tp_pct": 3.0
    }
  }
}
```

**Exit card** (`exit.rule_trigger`):
```json
{
  "type": "exit.rule_trigger",
  "slots": {
    "context": { "tf": "1d", "symbol": "BTC-USD" },
    "event": {
      "condition": {
        "type": "anyOf",
        "anyOf": [
          {
            "type": "regime",
            "regime": {
              "metric": "ret_pct",
              "tf": "1d",
              "op": ">=",
              "value": 3.0,
              "lookback_bars": 1
            }
          },
          {
            "type": "regime",
            "regime": {
              "metric": "ret_pct",
              "tf": "1d",
              "op": "<=",
              "value": -2.0,
              "lookback_bars": 1
            }
          }
        ]
      }
    },
    "action": {
      "mode": "close"
    },
    "risk": {
      "tp_pct": 3.0,
      "sl_pct": 2.0
    }
  }
}
```

This pattern (gate.time_filter + entry.rule_trigger) is the recommended approach for simple scheduled trading rules that don't require complex pattern matching.

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
4. **Execution order is automatic** - Gates automatically execute before entries/exits, overlays automatically execute after
5. **Use `compile_strategy`** - Always compile before marking strategy as "ready"
6. **Read schema examples** - Use `get_schema_example` to get valid slot configurations
7. **Validate slots** - Use `validate_slots_draft` before creating cards to catch errors early

## Agent Decision Rules: What Goes Where

**Critical**: Use these rules to map user intent to the correct schema components.

- **"How to Trade"** → Archetype (entry.*, exit.*, gate.*, overlay.*)
- **"When"** → ConditionSpec (use `type='regime'` for single conditions)
- **"How Much" / "How to Execute"** → SizingSpec / ExecutionSpec
- **"Risk"** → Exits or Overlays

**Examples**:
- "Buy on pullbacks" → `entry.trend_pullback`
- "Only trade in uptrend" → `gate.regime` with ConditionSpec(type='regime', regime={metric='trend_regime', ...})
- "Use limit orders 0.2% below" → `action.execution` with ExecutionSpec
- "Buy $1000 worth" → `action.sizing` with SizingSpec

## Tool Reference

- `get_archetypes(kind=None)` - List all archetypes, optionally filtered by kind
- `get_archetype_schema(type_id)` - Get full schema for an archetype
- `get_schema_example(type_id)` - Get ready-to-use example slots
- `validate_slots_draft(type_id, slots)` - Validate slots before creating card
- `create_card(type, slots)` - Create a card from an archetype
- `create_strategy(name, universe)` - Create a new strategy
- `attach_card(strategy_id, card_id, role)` - Attach card to strategy (execution order determined by role)
- `compile_strategy(strategy_id)` - Compile and validate strategy
- `validate_strategy(strategy_id)` - Check if strategy is ready to run

## Error Handling

All tools return structured errors with:
- `error_code`: Machine-readable error code
- `recovery_hint`: Actionable guidance for recovery
- `details`: Additional context

For transient errors (DATABASE_ERROR, NETWORK_ERROR, TIMEOUT_ERROR), the error message and recovery_hint will explicitly indicate that you should try again.

Common error codes:
- `ARCHETYPE_NOT_FOUND`: Archetype doesn't exist - use `get_archetypes` to see available types
- `SCHEMA_VALIDATION_ERROR`: Slot values don't match schema - use `get_schema_example` for valid values
- `VALIDATION_ERROR`: Invalid parameter - check error message for details
- `NOT_FOUND`: Resource not found - check ID spelling
- `DATABASE_ERROR`: Transient database error - the error message will indicate if you should try again

