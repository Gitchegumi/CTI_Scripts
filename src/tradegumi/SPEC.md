# TradeGumi AI-Augmented Trading Infrastructure

## Overview

TradeGumi is an AI-augmented trading infrastructure that captures market context at trade entry, analyzes historical patterns, and provides confidence-weighted decision support for trading signals.

## Core Principles

### Temporal Firewall (CRITICAL)

All market context must be captured **at entry timestamp**. No queries are allowed using data after entry time. This ensures:
- No look-ahead bias in pattern matching
- Frozen snapshot of conditions at decision point
- Clean separation between entry context and exit analysis

## System Components

### 1. Signal Processor (`signal_processor.py`)

**Purpose:** Intake and validate inbound trading signals

**Input Format (JSON):**
```json
{
  "signal_id": "uuid",
  "timestamp": "ISO8601",
  "symbol": "ES",
  "side": "long|short",
  "indicators": {
    "stochrsi": 0.75,
    "macd": 2.3,
    "macd_signal": 1.8,
    "atr": 4.5,
    "keltner_upper": 4520.5,
    "keltner_lower": 4480.25,
    "price": 4505.0
  },
  "session": "am|pm|overnight",
  "spread": 0.25
}
```

### 2. Context Snapshot (`context_snapshot.py`)

**Purpose:** Capture frozen market context at entry

**Captured Data:**
- All indicator values at entry
- Session type (AM/PM/overnight)
- Spread conditions
- News sentiment score (frozen at entry)
- Timestamp of capture

**Temporal Enforcement:**
- Context is immutable after creation
- news_sentiment_at_entry is never updated
- news_sentiment_at_exit is separate field for post-hoc analysis only

### 3. Pattern Analyzer (`pattern_analyzer.py`)

**Purpose:** Match current conditions against historical patterns

**Pattern Hash Algorithm:**
- Normalize indicators to buckets: 0-20, 20-40, 40-60, 60-80, 80-100
- Create hash from bucketized indicator states
- Hash format: `stochrsi_bucket|macd_bucket|atr_bucket|session`

**Query Pattern:**
```sql
SELECT * FROM pattern_performance 
WHERE pattern_hash = ?
```

**Return Data:**
- win_rate: float (0.0-1.0)
- expectancy: float (R-multiple)
- trade_count: int (similar historical trades)

### 4. Decision Engine (`decision_engine.py`)

**Purpose:** AI analysis and confidence scoring

**Output Format (JSON):**
```json
{
  "signal_id": "uuid",
  "decision": "approve|reject|modify",
  "confidence": 0.85,
  "size_adjustment": 1.0,
  "historical_context": {
    "win_rate": 0.72,
    "expectancy": 1.8,
    "trade_count": 45
  },
  "notes": "Strong pattern match, favorable session conditions"
}
```

**Decision Logic:**
- Confidence based on pattern match strength and sample size
- size_adjustment scales position based on confidence
- Reject if insufficient historical data (<5 similar trades)

### 5. Database (`database.py`)

**Purpose:** SQLite storage with temporal enforcement

#### Schema

**trades:**
- id (PRIMARY KEY)
- signal_id (UNIQUE)
- entry_timestamp
- exit_timestamp (nullable)
- symbol
- side (long|short)
- entry_price
- exit_price (nullable)
- outcome (win|loss|breakeven|open)
- pnl
- r_multiple

**entry_context:**
- id (PRIMARY KEY)
- signal_id (FOREIGN KEY → trades.signal_id)
- stochrsi
- macd
- macd_signal
- atr
- keltner_upper
- keltner_lower
- price
- session
- spread
- news_sentiment_at_entry (frozen)
- captured_at (timestamp)

**exit_context:**
- id (PRIMARY KEY)
- signal_id (FOREIGN KEY → trades.signal_id)
- exit_trigger
- news_sentiment_at_exit (post-hoc analysis only)
- recorded_at

**pattern_performance:**
- pattern_hash (PRIMARY KEY)
- description
- total_trades
- wins
- losses
- win_rate (computed)
- expectancy (computed)
- last_updated

### 6. Messaging (`messaging.py`)

**Purpose:** Discord integration for signal flow

**Channels:**
- Inbound: Signal reception from alert systems
- Outbound: Decision notifications to traders

**Message Flow:**
1. Receive signal via webhook/Discord
2. Process through decision engine
3. Return decision JSON to channel

### 7. Configuration (`.env.example`)

```bash
# Database
TRADEGUMI_DB_PATH=/path/to/tradegumi.db

# Discord Integration
TRADEGUMI_DISCORD_CHANNELS=incoming-signals,outgoing-decisions

# Optional
TRADEGUMI_LOG_LEVEL=INFO
TRADEGUMI_MIN_PATTERN_MATCHES=5
```

## Workflow

1. **Signal Arrival:** Webhook receives signal JSON
2. **Context Capture:** Freeze all indicators and market state
3. **Pattern Match:** Query historical patterns by hash
4. **AI Analysis:** Compute confidence and size adjustment
5. **Decision Output:** Send decision JSON back to channel
6. **Trade Recording:** Log entry context to database
7. **Exit Recording:** When trade closes, record exit context
8. **Pattern Update:** Recompute pattern_performance statistics

## Constraints

- No external API calls beyond Discord messaging
- All timestamps in UTC
- Pattern hashes use integer bucket boundaries (no floats)
- Minimum 5 historical matches required for approval
- Confidence scores capped at 0.95 without 50+ sample size

## Testing Requirements

- Unit tests for database schema and ORM
- Pattern hash consistency tests
- Temporal firewall validation (no future data leakage)
- Message format validation
