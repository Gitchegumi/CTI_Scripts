"use client";

import Link from "next/link";
import Header from "@/components/Header";
import AccountCard from "@/components/AccountCard";
import WatchlistSection from "@/components/WatchlistSection";
import SignalsSection from "@/components/SignalsSection";
import Footer from "@/components/Footer";
import SettingsPanel from "@/components/SettingsPanel";
import OpenTrades from "@/components/OpenTrades";
import TradeHistory from "@/components/TradeHistory";
import { useWatchlist, useSignals, useLoopState, useApiStatus, usePositions, useTradeHistory, useTradeCorrelations, useMarketOpen } from "@/hooks/useData";

export default function Home() {
  // Initial load with fast polling — once loopState arrives, useMarketOpen
  // will throttle everything to 60s on weekends/closed
  const { loopState } = useLoopState(true);
  const marketOpen = useMarketOpen(loopState);

  const { data, lastUpdated, error, isRefreshing } = useWatchlist(marketOpen);
  const { signals } = useSignals(marketOpen);
  const { status: apiStatus } = useApiStatus(5000);
  const { positions } = usePositions(marketOpen);
  const mode = apiStatus?.mode ?? "alert_only";
  const { trades, error: tradeHistoryError } = useTradeHistory(50, marketOpen, mode);
  const correlations = useTradeCorrelations();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header data={data} lastUpdated={lastUpdated} isRefreshing={isRefreshing} loopState={loopState} apiStatus={apiStatus} />

      {/* Nav links */}
      <div className="border-b border-slate-800 px-4 py-2 flex items-center gap-4 text-xs">
        <Link
          href="/journal"
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          📓 Signal Journal
        </Link>
        {mode === "alert_only" && (
          <Link
            href="/manual-trades"
            className="text-slate-500 hover:text-blue-400 transition-colors"
          >
            📝 Manual Trades
          </Link>
        )}
        <Link
          href="/strategy-metrics"
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          📊 Strategy Metrics
        </Link>
      </div>

      <main className="flex-1 px-4 py-4 max-w-7xl mx-auto w-full">
        {!marketOpen && (
          <div className="mb-4 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-yellow-400 text-center">
            🌙 Markets closed — polling throttled to 60s. Dashboard updates will resume when markets open.
          </div>
        )}
        {error ? (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400 text-sm">
            Failed to load watchlist: {error}
          </div>
        ) : data?.account ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left column: Account + Settings + Signals + Open Trades */}
            <div className="lg:col-span-1 space-y-4">
              <AccountCard account={data.account} />
              <SettingsPanel status={apiStatus} />
              <OpenTrades positions={positions} />
              <SignalsSection signals={signals} />
            </div>
            {/* Right column: Watchlist + Trade History */}
            <div className="lg:col-span-2 space-y-2">
              <WatchlistSection data={data} loopState={loopState?.symbols ?? []} />
              <TradeHistory trades={trades} correlations={correlations} error={tradeHistoryError} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
            Loading...
          </div>
        )}
      </main>

      {data?.account && <Footer data={data} apiStatus={apiStatus} />}
    </div>
  );
}
