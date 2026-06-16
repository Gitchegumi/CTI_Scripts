import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OpportunityExplorer } from "@/components/strategy-metrics/OpportunityExplorer";
import type { StrategyMetricOpportunity } from "@/types";

function opp(id: string, symbol: string): StrategyMetricOpportunity {
  return {
    id,
    symbol,
    evaluated_at: "2026-06-05T12:00:00Z",
    final_decision: "rejected",
    decision_reason: "criteria_failed",
    near_miss: false,
    failed_criteria_count: 1,
    criteria: [
      {
        criterion_name: "macd",
        layer: "signal_stack",
        measured_value: 0.1,
        threshold_value: 0.2,
        threshold_operator: "gte",
        passed: false,
        margin: -0.1,
        normalized_margin: null,
        required: true,
        blocked_signal: true,
        data_quality: "complete",
      },
    ],
  } as unknown as StrategyMetricOpportunity;
}

describe("OpportunityExplorer (US5)", () => {
  it("lists loaded opportunities and narrows on search (FR-021)", () => {
    render(
      <OpportunityExplorer
        opportunities={[opp("1", "EURUSD"), opp("2", "GBPUSD")]}
        totalEvaluated={2}
        loadingMore={false}
        onLoadMore={() => {}}
      />,
    );
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
    expect(screen.getByText("GBPUSD")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/search opportunities/i), { target: { value: "EUR" } });
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
    expect(screen.queryByText("GBPUSD")).not.toBeInTheDocument();
  });

  it("expands a row to reveal its criteria (FR-022)", () => {
    render(
      <OpportunityExplorer
        opportunities={[opp("1", "EURUSD")]}
        totalEvaluated={1}
        loadingMore={false}
        onLoadMore={() => {}}
      />,
    );
    expect(screen.queryByText("macd")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getByText("macd")).toBeInTheDocument();
  });

  it("offers Load more only when more remain, and is bounded (FR-021/SC-006)", () => {
    const onLoadMore = vi.fn();
    render(
      <OpportunityExplorer
        opportunities={[opp("1", "EURUSD"), opp("2", "GBPUSD")]}
        totalEvaluated={5}
        loadingMore={false}
        onLoadMore={onLoadMore}
      />,
    );
    const more = screen.getByRole("button", { name: /load more \(2 \/ 5\)/i });
    fireEvent.click(more);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });
});
