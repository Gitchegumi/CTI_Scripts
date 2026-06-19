import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import {
  LifecycleDrilldown,
  type LifecycleDrilldownState,
} from "@/components/strategy-metrics/LifecycleDrilldown";
import * as api from "@/lib/api";
import type { StrategyMetricLifecycleEvent } from "@/types";

vi.mock("@/lib/api", () => ({ getStrategyMetricLifecycleEvents: vi.fn() }));
const eventsMock = vi.mocked(api.getStrategyMetricLifecycleEvents);

const applied = { start: "2026-06-01", end: "2026-06-08" };

function openState(metric: string): LifecycleDrilldownState {
  return { open: true, metric, title: "Pullback Entries", description: "Pullback entries opened." };
}

function event(overrides: Partial<StrategyMetricLifecycleEvent> = {}): StrategyMetricLifecycleEvent {
  return {
    id: "evt-1",
    symbol: "EURUSD",
    timestamp: "2026-06-05T12:00:00Z",
    direction: "BUY",
    signal_type: "pullback",
    lifecycle_role: "entry",
    fields: [{ label: "TP extensions", value: 2 }],
    ...overrides,
  };
}

beforeEach(() => eventsMock.mockReset());

describe("LifecycleDrilldown (second-row card drill-down)", () => {
  it("fetches the metric's journal records and renders their fields", async () => {
    eventsMock.mockResolvedValue([event()]);
    render(<LifecycleDrilldown state={openState("pullback_entries")} appliedFilters={applied} onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText("EURUSD")).toBeInTheDocument());
    expect(eventsMock).toHaveBeenCalledWith(expect.objectContaining({ metric: "pullback_entries" }));
    expect(screen.getByText("TP extensions")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders object-valued fields as readable JSON", async () => {
    eventsMock.mockResolvedValue([
      event({ fields: [{ label: "Outcomes", value: [{ outcome: "invalidated_by_prime" }] }] }),
    ]);
    render(<LifecycleDrilldown state={openState("prime_suppressed")} appliedFilters={applied} onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText("Outcomes")).toBeInTheDocument());
    expect(screen.getByText(/invalidated_by_prime/)).toBeInTheDocument();
  });

  it("shows an explicit empty state when no records match", async () => {
    eventsMock.mockResolvedValue([]);
    render(<LifecycleDrilldown state={openState("sl_moves")} appliedFilters={applied} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/no records matched/i)).toBeInTheDocument());
  });
});
