# Schema Capabilities and Limitations

This document tracks what trading patterns can and cannot be represented in the current schema.

## ✅ Fully Representable

### Limit Orders / Limit Triggers
- **Status**: ✅ Fully representable (as of schema update)
- **How**: Use `ExecutionSpec` with `order_type="limit"` and `limit_price` or `limit_offset_pct`
- **Price Level Triggers**: Use `RegimeSpec` with `metric="price_level_touch"` or `metric="price_level_cross"` and `level_price` field
- **Example**: "Buy BTC when price touches $50,000 with a limit order at $49,950"
  ```json
  {
    "type": "entry.rule_trigger",
    "slots": {
      "event": {
        "condition": {
          "type": "regime",
          "regime": {
            "metric": "price_level_touch",
            "level_price": 50000,
            "op": "==",
            "value": true
          }
        }
      },
      "action": {
        "execution": {
          "order_type": "limit",
          "limit_price": 49950
        }
      }
    }
  }
  ```

### Trailing Limit Orders
- **Status**: ✅ Fully representable (as of schema update)
- **How**: Use `ExecutionSpec.trailing_limit` with `enabled=true` and `trail_offset_pct`
- **Example**: "Trailing buy limit 0.5% below current price"
  ```json
  {
    "action": {
      "execution": {
        "order_type": "limit",
        "trailing_limit": {
          "enabled": true,
          "trail_offset_pct": 0.5,
          "update_frequency": "bar_close"
        }
      }
    }
  }
  ```

### Volume-Based Triggers
- **Status**: ✅ Fully representable (as of schema update)
- **How**: Use `RegimeSpec` with volume metrics:
  - `metric="volume_pctile"` - Percentile rank of volume vs lookback
  - `metric="volume_spike"` - Volume exceeds threshold (requires `volume_threshold_pctile`)
  - `metric="volume_dip"` - Volume below threshold (requires `volume_threshold_pctile`)
- **Example**: "Buy when volume spike > 90th percentile"
  ```json
  {
    "event": {
      "condition": {
        "type": "regime",
        "regime": {
          "metric": "volume_spike",
          "volume_threshold_pctile": 90,
          "op": "==",
          "value": true,
          "lookback_bars": 200
        }
      }
    }
  }
  ```

## ⚠️ Partially Representable

### Trend Filtering (Supertrend)
- **Status**: ⚠️ Partially representable
- **What works**: 
  - Use `trend_regime` metric for up/down/range classification
  - Use `trend_ma_relation` for MA-based trend detection
  - Use `trend_adx` for trend strength filtering
- **What's missing**: 
  - Supertrend indicator specifically is not a primitive
  - Cannot replicate exact Supertrend calculation (ATR-based dynamic levels)
- **Workaround**: Use `trend_regime` or `trend_ma_relation` with appropriate thresholds to approximate trend filtering behavior
- **Example**: "Only trade when trend is up"
  ```json
  {
    "type": "gate.regime",
    "slots": {
      "event": {
        "regime": {
          "type": "regime",
          "regime": {
            "metric": "trend_regime",
            "op": "==",
            "value": "up",
            "ma_fast": 20,
            "ma_slow": 50
          }
        }
      }
    }
  }
  ```

## ❌ Not Representable (Future Enhancements)

### Liquidity Sweep / Stop Hunt
- **Status**: ✅ Fully representable (as of schema update)
- **How**: Use `RegimeSpec` with `metric="liquidity_sweep"` and `level_reference` for dynamic level detection
- **Pattern characteristics**:
  - Price breaks below a support/resistance level (stop hunt - triggers stop losses)
  - Price quickly reclaims that level (confirms the sweep was a false break)
  - Entry on the reclaim (buying the liquidity sweep)
- **Example**: "Buy when price sweeps below previous low then reclaims within 5 bars"
  ```json
  {
    "type": "entry.rule_trigger",
    "slots": {
      "event": {
        "condition": {
          "type": "regime",
          "regime": {
            "metric": "liquidity_sweep",
            "level_reference": "previous_low",
            "reclaim_within_bars": 5,
            "lookback_bars": 50,
            "op": "==",
            "value": true
          }
        }
      },
      "action": {
        "direction": "long"
      }
    }
  }
  ```
- **Dynamic level references**:
  - `previous_low` / `previous_high` - Lowest/highest price in lookback_bars
  - `recent_support` / `recent_resistance` - Support/resistance level detected in lookback_bars
  - `session_low` / `session_high` - Lowest/highest price in current session (requires session)
- **Also works with**: `price_level_cross` and `price_level_touch` now support `level_reference` instead of fixed `level_price` for dynamic level detection

### Momentum Flags / Pennants
- **Status**: ❌ Not representable as a named primitive
- **What's missing**: 
  - No `flag_pattern` or `pennant_pattern` metric in `RegimeSpec.metric`
  - No dedicated `entry.flag` or `entry.pennant` archetype
- **Pattern characteristics** (not directly expressible):
  - Initial strong momentum move
  - Consolidation period with narrowing price range
  - Decreasing volume during consolidation
  - Breakout continuation in direction of initial move
- **Partial workaround**: Can approximate using `ConditionSpec.sequence` to require:
  1. Initial momentum (`ret_pct` with high threshold)
  2. Volatility compression (`vol_bb_width_pctile` decreasing)
  3. Volume dip (`volume_dip`)
  4. Breakout (`BreakoutSpec` or `price_level_cross`)
- **Example workaround** (approximate):
  ```json
  {
    "type": "entry.rule_trigger",
    "slots": {
      "event": {
        "condition": {
          "type": "sequence",
          "sequence": [
            {
              "cond": {
                "type": "regime",
                "regime": {
                  "metric": "ret_pct",
                  "op": ">",
                  "value": 3.0,
                  "lookback_bars": 5
                }
              },
              "within_bars": 20
            },
            {
              "cond": {
                "type": "allOf",
                "allOf": [
                  {
                    "type": "regime",
                    "regime": {
                      "metric": "vol_bb_width_pctile",
                      "op": "<",
                      "value": 30,
                      "lookback_bars": 50
                    }
                  },
                  {
                    "type": "regime",
                    "regime": {
                      "metric": "volume_dip",
                      "volume_threshold_pctile": 25,
                      "op": "==",
                      "value": true,
                      "lookback_bars": 50
                    }
                  }
                ]
              },
              "within_bars": 30
            },
            {
              "cond": {
                "type": "regime",
                "regime": {
                  "metric": "price_level_cross",
                  "level_price": 50000,
                  "level_direction": "up",
                  "op": "==",
                  "value": true
                }
              },
              "within_bars": 20
            }
          ]
        }
      }
    }
  }
  ```
- **Limitation**: This workaround doesn't capture the exact geometric pattern (narrowing triangle/rectangle) that defines flags/pennants. It only approximates the sequence of events.
- **Future**: May add dedicated `flag_pattern` metric or `entry.flag` archetype in future releases

### Custom Indicators
- **Status**: ❌ Not representable
- **Reason**: Schema only includes built-in metrics. Custom indicator calculations cannot be expressed.
- **Workaround**: Use closest available metric or wait for indicator extensibility

### Multi-Leg Options Strategies
- **Status**: ❌ Not representable
- **Reason**: Schema is designed for single-asset spot trading (MVP constraint)
- **Future**: May be added in post-MVP releases

### Portfolio-Level Risk Management
- **Status**: ❌ Not representable
- **Reason**: MVP constraint enforces single-asset trading per strategy
- **Future**: May be added in post-MVP releases

## Schema Evolution Notes

### Recently Added (vNext)
- **Price Level Conditions**: `price_level_touch`, `price_level_cross` metrics with `level_price` and `level_direction` fields
- **Trailing Limit Orders**: `ExecutionSpec.trailing_limit` object with `trail_offset_pct` and update frequency controls
- **Volume Metrics**: `volume_pctile`, `volume_spike`, `volume_dip` metrics with `volume_threshold_pctile` field

### Planned Enhancements
- Indicator extensibility (custom indicators)
- Multi-asset strategies (post-MVP)
- Options strategies (post-MVP)
- More sophisticated trailing mechanisms (e.g., trailing stop with ATR-based distance)

