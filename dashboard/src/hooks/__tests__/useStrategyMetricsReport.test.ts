import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStrategyMetricsReport } from "@/hooks/useData";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getStrategyMetricsSummary: vi.fn(),
  getStrategyMetricOpportunities: vi.fn(),
}));

const summaryMock = vi.mocked(api.getStrategyMetricsSummary);
const oppsMock = vi.mocked(api.getStrategyMetricOpportunities);

const filters = { start: "2026-06-01", end: "2026-06-08" };
const fakeSummary = { total_evaluated: 3 } as unknown as Awaited<ReturnType<typeof api.getStrategyMetricsSummary>>;

beforeEach(() => {
  summaryMock.mockReset();
  oppsMock.mockReset();
});

describe("useStrategyMetricsReport (controlled execution)", () => {
  it("does not fetch until run() is called (FR-001/SC-001)", () => {
    renderHook(() => useStrategyMetricsReport());
    expect(summaryMock).not.toHaveBeenCalled();
    expect(oppsMock).not.toHaveBeenCalled();
  });

  it("fetches exactly once per run and exposes the report (FR-002)", async () => {
    summaryMock.mockResolvedValue(fakeSummary);
    oppsMock.mockResolvedValue([{ id: "o1" }] as never);
    const { result } = renderHook(() => useStrategyMetricsReport());

    await act(async () => {
      await result.current.run(filters);
    });

    expect(summaryMock).toHaveBeenCalledTimes(1);
    expect(oppsMock).toHaveBeenCalledTimes(1);
    expect(result.current.summary).toEqual(fakeSummary);
    expect(result.current.status).toBe("success");
  });

  it("ignores a duplicate run while one is in flight (FR-004)", async () => {
    // Stays pending so the first run holds the in-flight guard.
    summaryMock.mockReturnValue(new Promise(() => {}) as never);
    oppsMock.mockReturnValue(new Promise(() => {}) as never);
    const { result } = renderHook(() => useStrategyMetricsReport());

    await act(async () => {
      void result.current.run(filters); // starts, holds the guard
      void result.current.run(filters); // ignored while in flight
      await new Promise((r) => setTimeout(r, 0)); // let the dynamic import resolve
    });

    expect(summaryMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the last successful report visible on error (FR-005/SC-009)", async () => {
    summaryMock.mockResolvedValueOnce(fakeSummary);
    oppsMock.mockResolvedValueOnce([{ id: "o1" }] as never);
    const { result } = renderHook(() => useStrategyMetricsReport());

    await act(async () => { await result.current.run(filters); });
    expect(result.current.summary).toEqual(fakeSummary);

    summaryMock.mockRejectedValueOnce(new Error("boom"));
    oppsMock.mockResolvedValueOnce([] as never);
    await act(async () => { await result.current.run(filters); });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toContain("boom");
    expect(result.current.summary).toEqual(fakeSummary); // retained, not cleared
  });
});
