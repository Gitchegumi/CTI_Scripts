export interface RankedEntry {
  symbol: string;
  score: number;
  tier: string;
}

export interface AccountData {
  balance: number;
  nav: number;
  unrealized_pl: number;
  realized_pl: number;
  open_trades: number;
  start_balance: number;
  session_pnl: number;
  session_pnl_pct: number;
  cti_program: string;
  cti_phase: number;
  cti_phase_label: string;
  cti_challenge_type: string;
  cti_tier_name: string;
  cti_tier_dollars: number;
  active_target_pct: number;
  has_profit_target: boolean;
  profit_target_dollars: number;
  profit_target_remaining: number;
  profit_target_remaining_pct: number;
  daily_loss_limit: number;
  daily_loss_remaining: number;
  daily_loss_remaining_pct: number;
  max_dd_dollars: number;
  dd_remaining: number;
  dd_remaining_pct: number;
  daily_loss_pct: number;
  max_dd_pct: number;
}

export interface SignalEntry {
  symbol: string;
  direction: "BUY" | "SELL";
  confidence: number;
  strategy?: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  lot_size: number;
  atr: number;
  rr: number | null;
  timestamp: string;
  lifecycle_role?: "entry" | "management" | "warning" | "outcome" | "legacy_signal" | string;
  current_stop_loss?: number | null;
  current_take_profit?: number | null;
  entry_signal_type?: string | null;
  source_signal_type?: string | null;
}

export type SignalOutcomeStatus =
  | "pending"
  | "open_simulated"
  | "closed"
  | "ambiguous"
  | "invalidated"
  | "expired";

export type SignalOutcome =
  | "tp"
  | "sl"
  | "ambiguous"
  | "expired"
  | "manually_closed"
  | "invalidated_by_prime"
  | "invalidated_by_system"
  | "none";

export interface SignalJournalOutcomeFields {
  status?: SignalOutcomeStatus | string;
  outcome?: SignalOutcome | string;
  outcome_source?: string | null;
  exit_time?: string | null;
  exit_price?: number | null;
  outcome_checked_at?: string | null;
  observations_to_outcome?: number | null;
  bars_to_outcome?: number | null;
  max_favorable_excursion?: number | null;
  max_adverse_excursion?: number | null;
  ambiguous_reason?: string | null;
  manually_overridden?: boolean;
  manual_override_reason?: string | null;
}

export interface ManagedLifecycleFields {
  lifecycle_role?: "entry" | "management" | "warning" | "outcome" | "legacy_signal" | string;
  trade_id?: string | null;
  entry_signal_id?: string | null;
  entry_signal_type?: string | null;
  management_event_id?: string | null;
  source_signal_id?: string | null;
  source_signal_type?: string | null;
  management_accepted?: boolean | null;
  management_reason?: string | null;
  management_rejection_reason?: string | null;
  price_at_event?: number | null;
  old_stop_loss?: number | null;
  new_stop_loss?: number | null;
  old_take_profit?: number | null;
  new_take_profit?: number | null;
  current_stop_loss?: number | null;
  current_take_profit?: number | null;
  managed_exit_reason?: string | null;
  managed_result_category?: "win" | "loss" | "breakeven" | string | null;
  captured_r?: number | null;
}

export type TradeGrade =
  | "TP_HIT"
  | "SL_HIT"
  | "BE"
  | "MISSED_ENTRY"
  | "LATE_SIGNAL"
  | "DUPLICATE"
  | "INVALID"
  | "PENDING";

export interface ActiveSignal {
  latest: SignalEntry;
  count: number;
}

export interface SymbolState {
  symbol: string;
  state: string;
  trend: string;
  lr_1h: number;
  lr_15: number;
  lr_5: number;
  score: number;
  tier: string;
  bid?: number;
  ask?: number;
  spread?: number;
  // Additive forex-session diagnostics (specs/021-market-hours-rescan US3).
  // Optional so older loop_state files without these fields still parse.
  market_open?: boolean;
  availability_state?: "available" | "market_closed" | "symbol_unavailable";
  availability_reason?: string;
  session_boundary?: string | null;
}

export interface LoopState {
  timestamp: string;
  mode: string;
  provider: string;
  symbols: SymbolState[];
}

export interface WatchlistData {
  timestamp: string;
  tier1: string[];
  tier2: string[];
  below: string[];
  ranked: [string, number, string][];
  account: AccountData;
}

export interface OpenPosition {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  open_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pl: number;
  net_profit: number;
}

export interface ClosedTrade {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  open_price: number;
  close_price: number;
  open_time: string;
  close_time: string;
  realized_pl: number;
  financing: number;
  pnl: number;
  source?: "manual" | "execution_history" | string;
  source_trade_id?: string;
  bot_mode?: "alert_only" | "demo" | "live";
  notes?: string;
  tags?: string[];
  has_overrides?: boolean;
  permissions?: TradePermissions;
}

export interface TradeCorrelation {
  trade_id: string;
  symbol: string;
  direction: string;
  confidence: number;
  signal_timestamp: string;
  trade_timestamp: string;
  signal_lag_seconds: number;
}

// ── Manual Trades (alert-only backtesting) ───────────────────────────────────

export interface TradePermissions {
  can_edit_all_fields: boolean;
  can_edit_notes_tags: boolean;
  can_delete: boolean;
}

export interface ManualTrade {
  id: string;
  source: "manual" | "execution_history" | string;
  source_trade_id: string;
  bot_mode: "alert_only" | "demo" | "live";
  symbol: string;
  direction: "long" | "short";
  entry_price: number;
  exit_price: number | null;
  entry_time: string;
  exit_time: string | null;
  volume: number | null;
  fees: number;
  pnl: number;
  pnl_percent: number;
  status: "open" | "closed";
  notes: string;
  tags: string[];
  has_overrides: boolean;
  permissions: TradePermissions;
  created_at: string;
  updated_at: string;
}

export interface ManualTradeSummary {
  total_trades: number;
  closed_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  avg_pnl_percent: number;
}

export interface AgentExportRecord {
  id: string;
  source: string;
  symbol: string;
  direction: "long" | "short";
  status: "open" | "closed";
  entry_time: string;
  exit_time: string | null;
  pnl: number;
  pnl_percent: number;
  notes: string;
  tags: string[];
}

export interface AgentExport {
  schema_name: "Agent Export";
  schema_version: string;
  generated_at: string;
  bot_mode: "alert_only" | "demo" | "live";
  chunking: {
    chunk_index: number;
    chunk_count: number;
    record_offset: number;
    record_limit: number;
  };
  records: AgentExportRecord[];
}

export interface SignalJournalExportScope {
  grade?: "ALL" | TradeGrade | "MANUAL_CLOSE" | "EXPIRED";
  start?: string;
  end?: string;
  symbol?: string;
  status?: string;
  final_decision?: string;
  strategy?: string;
  mode?: string;
  graded_state?: "pending" | "graded";
  format: "csv";
}

// Strategy Metrics

export interface StrategyMetricCriterion {
  criterion_name: string;
  layer: string;
  measured_value: unknown;
  threshold_value: unknown;
  threshold_operator: string;
  passed: boolean | null;
  margin: number | null;
  normalized_margin: number | null;
  required: boolean;
  blocked_signal: boolean;
  data_quality: "complete" | "missing" | "malformed" | "not_applicable";
}

export interface StrategyMetricOpportunity {
  id: string;
  evaluated_at: string;
  symbol: string;
  timeframe: string;
  mode: string;
  strategy: string;
  direction: "BUY" | "SELL" | "none";
  trend: string;
  final_decision: "emitted" | "rejected" | "skipped" | "indeterminate";
  decision_reason: string;
  confidence: number | null;
  failed_criteria_count: number;
  near_miss: boolean;
  data_complete: boolean;
  data_quality_notes: string[];
  threshold_version: string;
  usable_for_strategy_stats?: boolean | null;
  stats_exclusion_reason?: string | null;
  lifecycle_role?: string | null;
  trade_id?: string | null;
  managed_exit_reason?: string | null;
  managed_result_category?: string | null;
  captured_r?: number | null;
  criteria: StrategyMetricCriterion[];
}

export interface StrategyCriterionSummary {
  criterion_name: string;
  evaluated_count: number;
  pass_count: number;
  fail_count: number;
  pass_rate: number;
  fail_rate: number;
  near_miss_contribution: number;
  average_failure_margin: number | null;
  incomplete_count: number;
}

export interface StrategyBlockerSummary {
  criterion_name: string;
  blocked_count: number;
  frequency_component: number;
  margin_component: number;
  quality_component: number;
  combined_score: number;
  example_opportunity_ids: string[];
}

export interface StrategyMetricsSummary {
  start: string;
  end: string;
  total_evaluated: number;
  emitted_count: number;
  trade_opportunity_count: number;
  stats_excluded_count: number;
  stats_unknown_eligibility_count: number;
  stats_exclusion_counts: Record<string, number>;
  total_prime_suppressed_signals: number;
  prime_suppressed_signals_by_symbol: Record<string, number>;
  prime_suppressed_same_direction_count: number;
  prime_suppressed_opposite_direction_count: number;
  prime_invalidated_by_prime_count: number;
  inferred_tp_close_count: number;
  inferred_sl_close_count: number;
  ambiguous_prime_close_count: number;
  managed_lifecycle_summary?: Record<string, unknown>;
  pullback_entries_opened: number;
  continuation_management_events_observed: number;
  continuation_management_events_accepted: number;
  continuation_management_events_rejected: number;
  tp_extension_count: number;
  sl_tighten_count: number;
  break_even_move_count: number;
  profit_protected_sl_win_count: number;
  opposite_direction_continuation_warning_count: number;
  average_r_captured: number | null;
  max_favorable_excursion_before_exit: number | null;
  managed_vs_original_result_delta: Record<string, number>;
  rejected_count: number;
  skipped_count: number;
  indeterminate_count: number;
  near_miss_count: number;
  criterion_summaries: StrategyCriterionSummary[];
  top_blockers: StrategyBlockerSummary[];
  data_quality_warnings: string[];
}

export interface StrategyMetricsComparison {
  baseline: StrategyMetricsSummary;
  comparison: StrategyMetricsSummary;
  deltas: {
    total_evaluated: number;
    emitted_count: number;
    near_miss_count: number;
    rejected_count: number;
    top_blocker_changed: boolean;
    baseline_top_blocker: string | null;
    comparison_top_blocker: string | null;
  };
}
