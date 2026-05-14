# Contract: Signal Journal Export API

## GET `/api/journal/export`

Exports Signal Journal records matching the selected scope.

### Query Parameters

| Name | Required | Description |
| --- | --- | --- |
| `start` | No | Inclusive start date/time for evaluated/created timestamp filtering |
| `end` | No | Inclusive end date/time for evaluated/created timestamp filtering |
| `grade` | No | Existing grade filter: `ALL`, `PENDING`, `TP_HIT`, `SL_HIT`, `MANUAL_CLOSE`, or `EXPIRED` |
| `symbol` | No | Optional current/future visible symbol filter |
| `status` | No | Optional current/future visible status filter |
| `final_decision` | No | Optional current/future visible decision filter |
| `strategy` | No | Optional current/future visible strategy filter |
| `mode` | No | Optional current/future visible mode filter |
| `graded_state` | No | Optional current/future visible graded/pending filter |

### Success Response

```text
Status: 200
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="signal-journal-2026-05-01-to-2026-05-14.csv"
```

Body is a CSV document with a header row and one row per matching Signal Journal record.

### Empty Selection Response

```text
Status: 404
Content-Type: application/json
```

```json
{
  "error": "No Signal Journal records match the selected export range."
}
```

### Invalid Selection Response

```text
Status: 400
Content-Type: application/json
```

```json
{
  "error": "start must be before end"
}
```

### Proxy Requirements

The dashboard proxy route at `/api/journal/export` must:

- Require the same journal authentication as the current route.
- Forward all recognized query parameters to the backend.
- Preserve `Content-Type`, `Content-Disposition`, and status from the backend for file responses.
- Return JSON errors without converting them to CSV or Blob downloads.
