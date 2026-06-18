import { describe, it, expect } from "vitest";
import {
  statsUseLabel,
  reachedTargetType,
  reachedTargetLabel,
} from "@/lib/journalLabels";

// ── statsUseLabel ────────────────────────────────────────────────────────────

describe("statsUseLabel", () => {
  it("maps known snake_case identifiers to readable labels", () => {
    expect(statsUseLabel("continuation_management_event")).toBe(
      "Continuation management event"
    );
    expect(statsUseLabel("duplicate_setup")).toBe("Duplicate setup");
    expect(statsUseLabel("late_signal")).toBe("Late signal");
    expect(statsUseLabel("stale_signal")).toBe("Stale signal");
    expect(statsUseLabel("manual_invalidated")).toBe("Manually invalidated");
    expect(statsUseLabel("missing_entry_context")).toBe(
      "Missing entry context"
    );
  });

  it("maps lifecycle roles", () => {
    expect(statsUseLabel("entry")).toBe("Entry");
    expect(statsUseLabel("management")).toBe("Management");
    expect(statsUseLabel("warning")).toBe("Warning");
    expect(statsUseLabel("legacy_signal")).toBe("Legacy signal");
  });

  it("maps management rejection reasons", () => {
    expect(statsUseLabel("insufficient_progress")).toBe(
      "Insufficient progress"
    );
    expect(statsUseLabel("risk_increase")).toBe("Risk increase");
    expect(statsUseLabel("extension_cap_reached")).toBe(
      "Extension cap reached"
    );
    expect(statsUseLabel("duplicate_management_event")).toBe(
      "Duplicate management event"
    );
  });

  it("maps managed result categories", () => {
    expect(statsUseLabel("win")).toBe("Win");
    expect(statsUseLabel("loss")).toBe("Loss");
    expect(statsUseLabel("breakeven")).toBe("Breakeven");
  });

  it("returns 'None' for null/undefined/empty", () => {
    expect(statsUseLabel(null)).toBe("None");
    expect(statsUseLabel(undefined)).toBe("None");
    expect(statsUseLabel("")).toBe("None");
  });

  it("falls back to title-case for unknown identifiers", () => {
    expect(statsUseLabel("some_unknown_reason")).toBe("Some Unknown Reason");
    expect(statsUseLabel("brand_new_exclusion")).toBe(
      "Brand New Exclusion"
    );
  });

  it("is case-insensitive for known mappings", () => {
    expect(statsUseLabel("CONTINUATION_MANAGEMENT_EVENT")).toBe(
      "Continuation management event"
    );
    expect(statsUseLabel("Duplicate_Setup")).toBe("Duplicate setup");
  });
});

// ── reachedTargetType ─────────────────────────────────────────────────────────

describe("reachedTargetType", () => {
  it("returns 'original' when current TP equals initial TP and TP was hit", () => {
    expect(
      reachedTargetType({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "TP_HIT",
      })
    ).toBe("original");
  });

  it("returns 'extended' when current TP differs from initial TP", () => {
    expect(
      reachedTargetType({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.108,
        trade_grade: "TP_HIT",
      })
    ).toBe("extended");
  });

  it("returns null when initial_take_profit is absent (cannot determine original vs extended)", () => {
    expect(
      reachedTargetType({
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "TP_HIT",
      })
    ).toBeNull();
  });

  it("returns null when TP was not hit", () => {
    expect(
      reachedTargetType({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "PENDING",
      })
    ).toBeNull();

    expect(
      reachedTargetType({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "SL_HIT",
      })
    ).toBeNull();
  });

  it("returns null when TP data is missing", () => {
    expect(
      reachedTargetType({
        trade_grade: "TP_HIT",
      })
    ).toBeNull(); // Not enough data to determine original vs extended
  });

  it("returns 'original' when outcome is 'tp' (not just grade)", () => {
    expect(
      reachedTargetType({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        outcome: "tp",
      })
    ).toBe("original");
  });
});

// ── reachedTargetLabel ───────────────────────────────────────────────────────

describe("reachedTargetLabel", () => {
  it("returns 'Original target' for original TP", () => {
    expect(
      reachedTargetLabel({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "TP_HIT",
      })
    ).toBe("Original target");
  });

  it("returns 'Extended target' for extended TP", () => {
    expect(
      reachedTargetLabel({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.108,
        trade_grade: "TP_HIT",
      })
    ).toBe("Extended target");
  });

  it("returns null when TP was not reached", () => {
    expect(
      reachedTargetLabel({
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
        trade_grade: "PENDING",
      })
    ).toBeNull();
  });
});

// ── Invalid continuation case ────────────────────────────────────────────────

describe("invalid continuation scenario", () => {
  it("label for continuation_management_event exclusion is readable", () => {
    // An invalid/orphan continuation is excluded from strategy stats
    // with stats_exclusion_reason = "continuation_management_event"
    expect(statsUseLabel("continuation_management_event")).toBe(
      "Continuation management event"
    );
  });

  it("reachedTargetType returns null for invalid continuation (no TP hit)", () => {
    expect(
      reachedTargetType({
        trade_grade: "INVALID",
        initial_take_profit: 1.104,
        take_profit: 1.104,
        current_take_profit: 1.104,
      })
    ).toBeNull();
  });
});