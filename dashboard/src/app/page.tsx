"use client";

import Header from "@/components/Header";
import AccountCard from "@/components/AccountCard";
import WatchlistSection from "@/components/WatchlistSection";
import SignalsSection from "@/components/SignalsSection";
import Footer from "@/components/Footer";
import { useWatchlist, useSignals, useLoopState } from "@/hooks/useData";

export default function Home() {
  const { data, lastUpdated, error, isRefreshing } = useWatchlist(60000);
  const { signals } = useSignals();
  const { loopState } = useLoopState();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header data={data} lastUpdated={lastUpdated} isRefreshing={isRefreshing} loopState={loopState} />

      <main className="flex-1 px-4 py-4 max-w-7xl mx-auto w-full">
        {error ? (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400 text-sm">
            Failed to load watchlist: {error}
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left column: Account + Signals */}
            <div className="lg:col-span-1 space-y-4">
              <AccountCard account={data.account} />
              <SignalsSection signals={signals} />
            </div>
            {/* Right column: Watchlist */}
            <div className="lg:col-span-2">
              <WatchlistSection data={data} loopState={loopState?.symbols ?? []} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
            Loading...
          </div>
        )}
      </main>

      {data && <Footer data={data} />}
    </div>
  );
}