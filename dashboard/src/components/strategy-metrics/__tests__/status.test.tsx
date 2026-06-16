import "@testing-library/jest-dom";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatusBadge, type CriterionStatus } from "@/components/strategy-metrics/status";

/**
 * FR-026 / SC-011: status meaning must never rely on color alone — every badge
 * pairs its color with a non-color cue (an icon and a text label).
 */
describe("StatusBadge non-color cues", () => {
  const statuses: CriterionStatus[] = ["pass", "fail", "near-miss", "blocker", "incomplete", "unavailable"];

  it.each(statuses)("renders an icon and a text label for status '%s'", (status) => {
    const { container, getByText } = render(<StatusBadge status={status} />);
    // Non-color cue 1: an svg icon
    expect(container.querySelector("svg")).toBeInTheDocument();
    // Non-color cue 2: a visible text label (not empty)
    const text = container.textContent?.trim() ?? "";
    expect(text.length).toBeGreaterThan(0);
    expect(getByText(text)).toBeInTheDocument();
  });
});
