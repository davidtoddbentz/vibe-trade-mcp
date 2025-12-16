# Disambiguation Question Bank

This document outlines the disambiguation questions that should be asked when user intent is ambiguous. These questions map directly to new schema capabilities (SizingSpec, ExecutionSpec, ConditionSpec).

**Principle**: Intent Intake still only "assumes meta"; Disambiguate asks only what cannot be safely defaulted.

## Sizing Questions

**When to ask**: When user mentions position size, trade amount, or capital allocation but doesn't specify the sizing mode.

### Multiple Choice Questions

1. **"How much per trade?"**
   - Fixed USD amount (e.g., "$1000 per trade")
   - Percentage of equity (e.g., "5% of account")
   - Fixed units/contracts (e.g., "10 shares")
   - Default (use strategy-level sizing)

2. **"What position size should we use?"**
   - Fixed dollar amount
   - Percentage of equity
   - Percentage of current position
   - Default (use strategy-level sizing)

### Free Form Questions

- "What dollar amount or percentage should each trade use?"
- "Do you want to risk a fixed dollar amount or a percentage of equity per trade?"

## Execution Questions

**When to ask**: When user mentions order type, limit orders, or execution style but doesn't specify details.

### Multiple Choice Questions

1. **"How should orders be placed?"**
   - Market order (immediate execution at current price)
   - Limit order (specify price offset or absolute price)
   - Stop order (triggered at specific price)
   - Default (market order)

2. **"What order type should we use?"**
   - Market (immediate)
   - Limit (with price offset)
   - Stop (triggered)
   - Default (market)

### Free Form Questions

- "Do you want to use market orders or limit orders? If limit, what price offset?"
- "Should we place limit orders? If so, how far from current price?"

## Condition Definition Questions

**When to ask**: When user uses vague terms like "bounce", "dip", "breakout" without specifying the exact condition.

### Multiple Choice Questions

1. **"What counts as 'bounce'?"**
   - Price crosses above moving average
   - Price moves from low to high within X bars
   - Price touches support and reverses
   - Default (use pattern-specific definition)

2. **"What defines a 'dip'?"**
   - Price below lower Bollinger Band
   - Price X% below recent high
   - Price crosses below moving average
   - Default (use pattern-specific definition)

3. **"What counts as a 'breakout'?"**
   - Price breaks above N-bar high
   - Price crosses above resistance level
   - Price moves X% above recent range
   - Default (use pattern-specific definition)

### Free Form Questions

- "Can you clarify what you mean by [vague_term]? What specific condition should trigger the entry?"
- "What exact condition should we use for [vague_term]?"

## Schedule Questions

**When to ask**: When user mentions timing, schedule, or recurring patterns but doesn't specify details.

### Multiple Choice Questions

1. **"When should it run?"**
   - Specific days of week (e.g., Monday-Friday)
   - Specific time window (e.g., 9:30 AM - 4:00 PM)
   - Specific days of month (e.g., 1st, 15th)
   - All the time (no schedule filter)

2. **"What timezone should we use?"**
   - UTC
   - America/New_York (US Eastern)
   - America/Los_Angeles (US Pacific)
   - Europe/London
   - Asia/Tokyo
   - Default (UTC)

### Free Form Questions

- "What days and times should this strategy run?"
- "Do you want to restrict trading to specific days or times?"

## Condition Composition Questions

**When to ask**: When user mentions multiple conditions (e.g., "trend filter + dip trigger") but doesn't specify logical operator.

### Multiple Choice Questions

1. **"How should we combine these conditions?"**
   - All must be true (AND / allOf)
   - Any can be true (OR / anyOf)
   - Sequence (first then second)
   - Default (allOf for multiple conditions)

### Free Form Questions

- "Should all conditions be true, or is any one sufficient?"
- "Do these conditions need to happen in sequence or simultaneously?"

## Examples

### Example 1: Sizing Disambiguation

**User**: "I want to trade BTC with $5000"

**Question**: "How much per trade?"
- Fixed USD amount ($5000 per trade)
- Percentage of equity (5% of account)
- Default (use strategy-level sizing)

### Example 2: Execution Disambiguation

**User**: "Buy BTC when it dips, but use limit orders"

**Question**: "How should limit orders be placed?"
- Market order (immediate execution)
- Limit order with price offset (e.g., 0.2% below current)
- Limit order with absolute price
- Default (market order)

### Example 3: Condition Disambiguation

**User**: "Buy when BTC bounces from the low"

**Question**: "What counts as 'bounce'?"
- Price crosses above moving average
- Price moves from low to high within X bars
- Price touches support and reverses
- Default (use pattern-specific definition)

### Example 4: Schedule Disambiguation

**User**: "Trade only during market hours"

**Question**: "When should it run?"
- Specific days of week (Monday-Friday)
- Specific time window (9:30 AM - 4:00 PM Eastern)
- All the time (no schedule filter)

### Example 5: Condition Composition

**User**: "Buy on dip but only if in uptrend"

**Question**: "How should we combine these conditions?"
- All must be true (dip AND uptrend)
- Any can be true (dip OR uptrend)
- Sequence (uptrend first, then dip)
- Default (all must be true)

## Implementation Notes

1. **Only ask when ambiguous**: If user clearly specifies (e.g., "use limit orders 0.2% below"), don't ask.
2. **Default safely**: If user doesn't care, use sensible defaults (market orders, strategy-level sizing).
3. **Context-aware**: Use previous conversation context to avoid redundant questions.
4. **Progressive disclosure**: Ask most important questions first (sizing, execution) before details.

