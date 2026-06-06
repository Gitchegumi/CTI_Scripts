# Data Model: High-Value KC Band Pullbacks

## Entity: Signal

The `Signal` dataclass represents a trade signal emitted by the CTI Signal Engine.

### Modified Fields
- **signal_type**: Expanded to support `"high_value_pullback"` in addition to `"pullback"` and `"continuation"`.

### Attributes
- `symbol`: str (e.g. `"EUR_USD"`)
- `direction`: str (`"BUY"` or `"SELL"`)
- `entry_price`: float
- `stop_loss`: float
- `take_profit`: float
- `atr`: float
- `lot_size`: float
- `risk_pct`: float
- `confidence`: float
- `breakdown`: dict (per-indicator confidence breakdown)
- `trend_direction`: str
- `patterns_found`: list
- `strategy`: str (e.g. `"CTI-v1.2-pullback"`)
- `signal_type`: str (`"pullback"`, `"continuation"`, or `"high_value_pullback"`)
- `pullback_trigger`: Optional[str]
- `pullback_bridge_status`: Optional[str]
- `pullback_rejection_reason`: Optional[str]

---

## Entity: EvaluatedOpportunity

Represents an evaluated opportunity stored in SQLite and written to state JSON files.

### Attributes
- `id`: str (unique identifier `{symbol}:{timestamp}`)
- `symbol`: str
- `mode`: str
- `direction`: str
- `trend`: str
- `final_decision`: str
- `decision_reason`: str
- `confidence`: float
- `signal_type`: str (`"pullback"`, `"continuation"`, or `"high_value_pullback"`)
