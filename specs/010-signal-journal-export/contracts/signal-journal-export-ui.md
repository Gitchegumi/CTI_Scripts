# Contract: Signal Journal Export UI

## Signal Journal Page Export Controls

The Signal Journal page provides export controls near the existing export action.

### Inputs

| Control | Rule |
| --- | --- |
| Start date/time | Optional inclusive lower boundary |
| End date/time | Optional inclusive upper boundary |
| Grade filter | Reuses the existing visible grade filter |
| Export button | Disabled while export is in progress |

### Behavior

- Clicking export sends the selected date/time range and current visible grade filter to `/api/journal/export`.
- When the response is a successful file response, the page reads it as a Blob, creates a temporary object URL, clicks a temporary download link, and revokes the object URL.
- The download filename comes from `Content-Disposition` when present and falls back to a deterministic local Signal Journal filename.
- When the response is a JSON error, the page shows the message and does not create a download link.
- When the selected range has no records, the page shows a clear no-records message and no file is downloaded.
- Existing journal loading, grouping, grading, notes, reset-to-pending, purge, and filter behavior remain unchanged.
