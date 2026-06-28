/**
 * Master-record selection and continuation (management-event) display logic
 * for the Signal Journal.
 *
 * A grouped journal record keeps its *original opening record* as the Master
 * for the group's entire lifecycle. Continuation signals are recorded as
 * management events and must never replace the Master, so grading and the
 * summary panel always reflect the opening record rather than the newest
 * related row.
 */

/** Lifecycle roles that represent continuation management evidence, not openings. */
const MANAGEMENT_ROLES = new Set(["management", "warning"]);

const ROLE_ENTRY = "entry";

interface LifecycleEntry {
  signal_id: string;
  lifecycle_role?: string | null;
}

interface ContinuationEntry {
  management_accepted?: boolean | null;
  management_reason?: string | null;
  management_rejection_reason?: string | null;
}

/** Display summary for a continuation management event row. */
export interface ContinuationEventSummary {
  /** True when the continuation was accepted and applied stop/target changes. */
  valid: boolean;
  /** Heading label: "Valid continuation" or "Invalid continuation". */
  label: string;
  /** Whether updated stop/target values should be shown (valid events only). */
  showUpdatedLevels: boolean;
  /** Reason key for an invalid event (run through statsUseLabel); null when valid. */
  rejectionReason: string | null;
}

function role(entry: { lifecycle_role?: string | null }): string {
  return String(entry.lifecycle_role ?? "").trim().toLowerCase();
}

/**
 * Return whether an entry is a continuation management event rather than an
 * opening record. Management and opposite-direction warning rows are evidence
 * attached to an existing trade and can never become the group's Master.
 */
export function isManagementEvent(entry: { lifecycle_role?: string | null }): boolean {
  return MANAGEMENT_ROLES.has(role(entry));
}

/**
 * Select the Master record for a grouped journal record.
 *
 * Entries are ordered oldest → newest. The Master is the original opening
 * record: an explicit managed-trade `entry`, otherwise the oldest
 * non-management record, otherwise the oldest record. Because continuation and
 * warning events are skipped, a newer continuation can never replace the
 * Master once an opening record exists in the group.
 */
export function pickMasterEntry<T extends LifecycleEntry>(entries: T[]): T {
  return (
    entries.find((e) => role(e) === ROLE_ENTRY) ??
    entries.find((e) => !isManagementEvent(e)) ??
    entries[0]
  );
}

/**
 * Summarize a continuation management event for display.
 *
 * A valid (accepted) continuation applied updated stop and target values; an
 * invalid (rejected) continuation applied no change and is labeled invalid.
 */
export function continuationEventSummary(entry: ContinuationEntry): ContinuationEventSummary {
  const valid = entry.management_accepted === true;
  return {
    valid,
    label: valid ? "Valid continuation" : "Invalid continuation",
    showUpdatedLevels: valid,
    rejectionReason: valid
      ? null
      : entry.management_rejection_reason ?? entry.management_reason ?? null,
  };
}
