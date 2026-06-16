import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CriterionDrilldown } from "@/components/strategy-metrics/CriterionDrilldown";
import * as api from "@/lib/api";
import type { StrategyMetricOpportunity, StrategyMetricsSummary } from "@/types";

vi.mock("@/lib/api", () => ({ getStrategyMetricOpportunities: vi.fn() }));
const oppsMock = vi.mocked(api.getStrategyMetricOpportunities);

const applied = { start: "2026-06-01", end: "2026-06-08" };

function summaryFor(evaluated: number): StrategyMetricsSummary {
  return {
    criterion_summaries: [
      {
        criterion_name: "macd",
        layer: "signal_stack",
        evaluated_count: evaluated,
        pass_count: 2,
        fail_count: 3,
        pass_rate: 0.4,
        fail_rate: 0.6,
        near_miss_contribution: 1,
        average_failure_margin: -0.1,
        incomplete_count: 0,
      },
    ],
  } as unknown as StrategyMetricsSummary;
}

function failingOpp(): StrategyMetricOpportunity {
  return {
    id: "o1",
    symbol: "EURUSD",
    evaluated_at: "2026-06-05T12:00:00Z",
    final_decision: "rejected",
    decision_reason: "macd_block",
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
        expected_pass: false,
        margin: -0.1,
        normalized_margin: null,
        required: true,
        blocked_signal: true,
        data_quality: "complete",
      },
    ],
  } as unknown as StrategyMetricOpportunity;
}

beforeEach(() => oppsMock.mockReset());

describe("CriterionDrilldown (US2)", () => {
  it("loads failures for the selected criterion and shows measured/threshold detail (FR-014/FR-023)", async () => {
    oppsMock.mockResolvedValue([failingOpp()]);
    render(<CriterionDrilldown criterionName="macd" appliedFilters={applied} summary={summaryFor(5)} onClose={() => {}} />);

    await waitFor(() => expect(screen.getByText("0.1")).toBeInTheDocument());
    expect(oppsMock).toHaveBeenCalledWith(expect.objectContaining({ criterion: "macd" }));
    expect(screen.getByText(/gte 0.2/)).toBeInTheDocument();
    expect(screen.getAllByText("signal_stack").length).toBeGreaterThan(0);
  });

  it("shows an explicit no-data state when the criterion had no evaluations (FR-017)", async () => {
    oppsMock.mockResolvedValue([]);
    render(<CriterionDrilldown criterionName="macd" appliedFilters={applied} summary={summaryFor(0)} onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/no opportunities evaluated this criterion/i)).toBeInTheDocument(),
    );
  });
});
