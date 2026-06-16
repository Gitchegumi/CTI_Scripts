import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReportControls } from "@/components/strategy-metrics/ReportControls";

const applied = { start: "2026-06-01", end: "2026-06-08" };

describe("ReportControls (US1 controlled execution)", () => {
  it("does not call onApply while editing fields (FR-001)", () => {
    const onApply = vi.fn();
    render(<ReportControls appliedFilters={applied} loading={false} onApply={onApply} onExport={() => {}} />);
    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "EURUSD" } });
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-06-02" } });
    expect(onApply).not.toHaveBeenCalled();
  });

  it("calls onApply once when Apply is activated (FR-002)", () => {
    const onApply = vi.fn();
    render(<ReportControls appliedFilters={applied} loading={false} onApply={onApply} onExport={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0]).toMatchObject({ start: "2026-06-01", end: "2026-06-08" });
  });

  it("blocks Apply and shows a message for an invalid date range (FR-006)", () => {
    const onApply = vi.fn();
    render(
      <ReportControls
        appliedFilters={{ start: "2026-06-08", end: "2026-06-01" }}
        loading={false}
        onApply={onApply}
        onExport={() => {}}
      />,
    );
    const apply = screen.getByRole("button", { name: /apply filters/i });
    expect(apply).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(/start date must be on or before/i);
    fireEvent.click(apply);
    expect(onApply).not.toHaveBeenCalled();
  });

  it("disables Apply while a report is loading (FR-003/FR-004)", () => {
    render(<ReportControls appliedFilters={applied} loading={true} onApply={() => {}} onExport={() => {}} />);
    expect(screen.getByRole("button", { name: /running/i })).toBeDisabled();
  });
});
