"use client";

import { AccountData } from "@/types";

interface AccountCardProps {
  account: AccountData;
}

function ProgressBar({
  label,
  remaining,
  total,
  colorClass,
}: {
  label: string;
  remaining: number;
  total: number;
  colorClass: string;
}) {
  const pct = total > 0 ? Math.round((remaining / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span>
          ${remaining.toFixed(0)} ({pct}%)
        </span>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function getBarColor(pct: number): string {
  if (pct > 50) return "bg-green-500";
  if (pct > 25) return "bg-yellow-500";
  return "bg-red-500";
}

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export default function AccountCard({ account }: AccountCardProps) {
  const pnlColor = account.session_pnl >= 0 ? "text-green-400" : "text-red-400";
  const pnlSign = account.session_pnl >= 0 ? "+" : "";

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">💳 Account Metrics</span>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 text-xs font-bold rounded bg-purple-600 text-purple-100">
            {account.cti_phase_label}
          </span>
          {account.open_trades > 0 && (
            <span className="px-2 py-0.5 text-xs rounded bg-orange-600 text-orange-100">
              {account.open_trades} open
            </span>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Balances */}
        <div className="flex flex-wrap gap-6">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wide">Balance</div>
            <div className="text-lg font-semibold text-white">${fmt(account.balance)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wide">NAV</div>
            <div className="text-lg font-semibold text-white">${fmt(account.nav)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wide">Session PnL</div>
            <div className={`text-lg font-semibold ${pnlColor}`}>
              {pnlSign}${fmt(Math.abs(account.session_pnl))}
            </div>
          </div>
        </div>

        {/* Progress bars */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <ProgressBar
            label="Profit Target"
            remaining={account.profit_target_remaining}
            total={account.profit_target_dollars}
            colorClass={getBarColor(Math.round(account.profit_target_remaining_pct))}
          />
          <ProgressBar
            label="Daily Loss Buffer"
            remaining={account.daily_loss_remaining}
            total={account.daily_loss_limit}
            colorClass={getBarColor(Math.round(account.daily_loss_remaining_pct))}
          />
          <ProgressBar
            label="Max Drawdown Buffer"
            remaining={account.dd_remaining}
            total={account.max_dd_dollars}
            colorClass={getBarColor(Math.round(account.dd_remaining_pct))}
          />
        </div>
      </div>
    </div>
  );
}