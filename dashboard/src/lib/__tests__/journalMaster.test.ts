import { describe, it, expect } from "vitest";
import {
  isManagementEvent,
  pickMasterEntry,
  continuationEventSummary,
} from "@/lib/journalMaster";

// ── isManagementEvent ─────────────────────────────────────────────────────────

describe("isManagementEvent", () => {
  it("treats management and warning roles as management events", () => {
    expect(isManagementEvent({ lifecycle_role: "management" })).toBe(true);
    expect(isManagementEvent({ lifecycle_role: "warning" })).toBe(true);
    expect(isManagementEvent({ lifecycle_role: "MANAGEMENT" })).toBe(true);
  });

  it("treats opening roles as non-management", () => {
    expect(isManagementEvent({ lifecycle_role: "entry" })).toBe(false);
    expect(isManagementEvent({ lifecycle_role: "legacy_signal" })).toBe(false);
    expect(isManagementEvent({ lifecycle_role: null })).toBe(false);
    expect(isManagementEvent({})).toBe(false);
  });
});

// ── pickMasterEntry ───────────────────────────────────────────────────────────

describe("pickMasterEntry", () => {
  it("keeps the original opening entry as Master even when a newer continuation exists", () => {
    const entries = [
      { signal_id: "open", lifecycle_role: "entry" },
      { signal_id: "cont-1", lifecycle_role: "management" },
      { signal_id: "cont-2", lifecycle_role: "management" },
    ];
    // Newest is cont-2, but the opening record must remain Master.
    expect(pickMasterEntry(entries).signal_id).toBe("open");
  });

  it("does not let an opposite-direction warning become Master", () => {
    const entries = [
      { signal_id: "open", lifecycle_role: "entry" },
      { signal_id: "warn", lifecycle_role: "warning" },
    ];
    expect(pickMasterEntry(entries).signal_id).toBe("open");
  });

  it("falls back to the oldest non-management record when no explicit entry role exists", () => {
    const entries = [
      { signal_id: "legacy", lifecycle_role: "legacy_signal" },
      { signal_id: "cont", lifecycle_role: "management" },
    ];
    expect(pickMasterEntry(entries).signal_id).toBe("legacy");
  });

  it("falls back to the oldest record when every entry is a management event", () => {
    const entries = [
      { signal_id: "cont-1", lifecycle_role: "management" },
      { signal_id: "cont-2", lifecycle_role: "warning" },
    ];
    expect(pickMasterEntry(entries).signal_id).toBe("cont-1");
  });

  it("returns the only entry for a single-record group", () => {
    const entries = [{ signal_id: "solo", lifecycle_role: "entry" }];
    expect(pickMasterEntry(entries).signal_id).toBe("solo");
  });
});

// ── continuationEventSummary ──────────────────────────────────────────────────

describe("continuationEventSummary", () => {
  it("labels an accepted continuation valid and shows updated levels", () => {
    const summary = continuationEventSummary({ management_accepted: true });
    expect(summary.valid).toBe(true);
    expect(summary.label).toBe("Valid continuation");
    expect(summary.showUpdatedLevels).toBe(true);
    expect(summary.rejectionReason).toBeNull();
  });

  it("labels a rejected continuation invalid with no updated levels", () => {
    const summary = continuationEventSummary({
      management_accepted: false,
      management_rejection_reason: "insufficient_progress",
    });
    expect(summary.valid).toBe(false);
    expect(summary.label).toBe("Invalid continuation");
    expect(summary.showUpdatedLevels).toBe(false);
    expect(summary.rejectionReason).toBe("insufficient_progress");
  });

  it("falls back to management_reason when no rejection reason is present", () => {
    const summary = continuationEventSummary({
      management_accepted: false,
      management_reason: "no_active_trade",
    });
    expect(summary.rejectionReason).toBe("no_active_trade");
  });

  it("treats a missing acceptance flag as invalid", () => {
    expect(continuationEventSummary({}).valid).toBe(false);
  });
});
