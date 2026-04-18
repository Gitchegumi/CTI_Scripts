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
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  lot_size: number;
  atr: number;
  rr: number;
  timestamp: string;
}

export interface SymbolState {
  symbol: string;
  state: string;
  trend: string;
  lr_15: number;
  lr_5: number;
  score: number;
  tier: string;
  bid?: number;
  ask?: number;
  spread?: number;
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