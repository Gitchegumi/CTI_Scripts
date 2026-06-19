import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { metricDisplay } from "@/lib/metrics-availability";
import { ExecutiveSummary } from "@/components/strategy-metrics/ExecutiveSummary";
import type { StrategyMetricsSummary } from "@/types";

describe("metrics-availability (US3, FR-008/FR-009)", () => {
  it("treats 0 as a real zero", () => {
    const d = metricDisplay(0);
    expect(d.available).toBe(true);
    expect(d.isZero).toBe(true);
    expect(d.text).toBe("0");
  });

  it("treats null/undefined/NaN as unavailable", () => {
    expect(metricDisplay(null).available).toBe(false);
    expect(metricDisplay(undefined).available).toBe(false);
    expect(metricDisplay(Number.NaN).available).toBe(false);
    expect(metricDisplay(null).text).toBe("—");
  });
});

function summaryWith(overrides: Partial<StrategyMetricsSummary>): StrategyMetricsSummary {
  return {
    total_evaluated: 0,
    emitted_count: 0,
    rejected_count: 0,
    skipped_count: 0,
    indeterminate_count: 0,
    near_miss_count: 0,
    trade_opportunity_count: 0,
    stats_excluded_count: 0,
    total_prime_suppressed_signals: 0,
    pullback_entries_opened: 0,
    continuation_management_events_observed: 0,
    continuation_management_events_accepted: 0,
    continuation_management_events_rejected: 0,
    sl_tighten_count: 0,
    break_even_move_count: 0,
    tp_extension_count: 0,
    average_r_captured: null,
    managed_vs_original_result_delta: { improved: 0, worsened: 0 },
    ...overrides,
  } as unknown as StrategyMetricsSummary;
}

describe("ExecutiveSummary rendering (US3)", () => {
  it("renders a real zero and an unavailable metric distinctly", () => {
    render(<ExecutiveSummary summary={summaryWith({ total_evaluated: 0, average_r_captured: null })} />);
    // A real zero is shown as "0"
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
    // An unavailable metric (average_r_captured === null) is marked, not shown as 0
    expect(screen.getAllByText(/Unavailable/i).length).toBeGreaterThan(0);
  });

  it("shows a populated value when available", () => {
    render(<ExecutiveSummary summary={summaryWith({ total_evaluated: 1234 })} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });
});

describe("ExecutiveSummary second-row lifecycle drill-down", () => {
  it("opens the lifecycle drilldown with the right metric for a non-zero card", () => {
    const onLifecycleClick = vi.fn();
    render(
      <ExecutiveSummary
        summary={summaryWith({ pullback_entries_opened: 5 })}
        onLifecycleClick={onLifecycleClick}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pullback entries/i }));
    expect(onLifecycleClick).toHaveBeenCalledWith(
      expect.objectContaining({ metric: "pullback_entries" }),
    );
  });

  it("maps Rejected mgmt and SL moves to their lifecycle metrics", () => {
    const onLifecycleClick = vi.fn();
    render(
      <ExecutiveSummary
        summary={summaryWith({ continuation_management_events_rejected: 3, sl_tighten_count: 2 })}
        onLifecycleClick={onLifecycleClick}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Rejected mgmt/i }));
    fireEvent.click(screen.getByRole("button", { name: /SL moves/i }));
    expect(onLifecycleClick).toHaveBeenNthCalledWith(1, expect.objectContaining({ metric: "continuation_rejected" }));
    expect(onLifecycleClick).toHaveBeenNthCalledWith(2, expect.objectContaining({ metric: "sl_moves" }));
  });

  it("leaves a zero-valued second-row card non-clickable", () => {
    const onLifecycleClick = vi.fn();
    render(
      <ExecutiveSummary
        summary={summaryWith({ total_prime_suppressed_signals: 0 })}
        onLifecycleClick={onLifecycleClick}
      />,
    );
    expect(screen.queryByRole("button", { name: /Prime suppressed/i })).toBeNull();
  });
});
