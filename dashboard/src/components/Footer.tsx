"use client";

import { WatchlistData } from "@/types";

interface FooterProps {
  data: WatchlistData;
}

export default function Footer({ data }: FooterProps) {
  const { account } = data;
  const program = account.cti_program
    ? account.cti_program.charAt(0).toUpperCase() + account.cti_program.slice(1)
    : "—";

  return (
    <footer className="border-t border-slate-700 px-4 py-3 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
      <div className="flex flex-wrap gap-4">
        <span>
          <span className="text-slate-400">Program:</span>{" "}
          <span className="text-slate-300">{program}</span>
        </span>
        <span>
          <span className="text-slate-400">Phase:</span>{" "}
          <span className="text-slate-300">{account.cti_phase_label}</span>
        </span>
      </div>
      <div className="flex flex-wrap gap-4">
        <span>
          Daily Loss Limit:{" "}
          <span className="text-slate-300">${account.daily_loss_limit.toFixed(0)} ({(account.daily_loss_pct * 100).toFixed(0)}%)</span>
        </span>
        <span>
          Max Drawdown:{" "}
          <span className="text-slate-300">${account.max_dd_dollars.toFixed(0)} ({(account.max_dd_pct * 100).toFixed(0)}%)</span>
        </span>
      </div>
    </footer>
  );
}