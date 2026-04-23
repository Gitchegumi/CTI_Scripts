"use client";

import { WatchlistData } from "@/types";
import { ApiStatus } from "@/lib/api";

interface FooterProps {
  data: WatchlistData;
  apiStatus?: ApiStatus | null;
}

const PHASE_LABELS: Record<number, string> = {
  1: "Phase 1",
  2: "Phase 2",
  3: "Funded",
};

export default function Footer({ data, apiStatus }: FooterProps) {
  const { account } = data;

  const challenge_type = apiStatus?.challenge_type
    ? apiStatus.challenge_type.charAt(0).toUpperCase() + apiStatus.challenge_type.slice(1)
    : account.cti_challenge_type
      ? account.cti_challenge_type.charAt(0).toUpperCase() + account.cti_challenge_type.slice(1)
      : "—";

  const phase = apiStatus
    ? PHASE_LABELS[apiStatus.phase] ?? `Phase ${apiStatus.phase}`
    : account.cti_phase_label ?? "—";

  return (
    <footer className="border-t border-slate-700 px-4 py-3 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
      <div className="flex flex-wrap gap-4">
        <span>
          <span className="text-slate-400">Challenge Type:</span>{" "}
          <span className="text-slate-300">{challenge_type}</span>
        </span>
        <span>
          <span className="text-slate-400">Phase:</span>{" "}
          <span className="text-slate-300">{phase}</span>
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
