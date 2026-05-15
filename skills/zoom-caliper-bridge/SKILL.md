---
name: zoom-caliper-bridge
description: >
  Map Zoom meeting participant events to 1EdTech Caliper v1p2 SessionEvents and
  send them to a Caliper or Unizin endpoint. Use this skill whenever the user
  mentions Caliper, Unizin, LMS analytics, forwarding Zoom attendance to
  Caliper, or converting Zoom meeting events into a Caliper SessionEvent
  envelope.
---

# Zoom Caliper Bridge

Transform Zoom meeting participant events into 1EdTech Caliper Analytics v1p2
`SessionEvent` envelopes and deliver them to a Caliper-compatible endpoint.

## When to Use

- A Zoom meeting event arrives and must be recorded as a Caliper `SessionEvent`.
- The user wants to send Zoom meeting attendance data to Unizin or another Caliper endpoint.
- Integration between Zoom and an LMS analytics pipeline via Caliper is needed.

## Examples

- "Send this Zoom meeting event to Unizin as a Caliper SessionEvent."
- "Map Zoom attendance into Caliper for our LMS analytics pipeline."
- "Generate the Caliper envelope for this participant join event and forward it."

## Workflow

1. Collect required inputs: `meeting_id`, `user_id`, `caliper_endpoint`, `caliper_api_key`.
2. Optionally collect: `action` (default `LoggedIn`), `lms_id`, `sis_id`.
3. Run the script:

```bash
python $SYNORA_ROOT/skills/customized/zoom-caliper-bridge/scripts/main.py \
  --meeting-id <MEETING_ID> \
  --user-id <USER_ID> \
  --action <ACTION> \
  --caliper-endpoint <ENDPOINT_URL> \
  --caliper-api-key <API_KEY> \
  [--lms-id <LMS_IDENTIFIER>] \
  [--sis-id <SIS_IDENTIFIER>] \
  [--dry-run]
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--meeting-id` | Yes | — | Zoom meeting ID |
| `--user-id` | Yes | — | Zoom user ID of the participant |
| `--action` | No | `LoggedIn` | Caliper action such as `LoggedIn` or `LoggedOut` |
| `--caliper-endpoint` | Yes | — | Caliper or Unizin endpoint URL |
| `--caliper-api-key` | Yes | — | Bearer token for the Caliper endpoint |
| `--lms-id` | No | — | LMS system identifier for the user |
| `--sis-id` | No | — | SIS system identifier for the user |
| `--dry-run` | No | `false` | Validate the mapping without sending data |

## What the Script Does

1. Looks up meeting info via `search_meeting`.
2. Looks up user info via `search_contact`.
3. Builds a Caliper v1p2 `EventEnvelope` containing a `SessionEvent`.
4. POSTs the envelope to the target Caliper endpoint with Bearer auth.
5. Prints the response, including accepted event IDs when available.

## Expected Caliper Response

```json
{
  "accepted_events": [
    {
      "id": "urn:uuid:...",
      "topics": {
        "caliper-all": "...",
        "silver": "..."
      }
    }
  ]
}
```

## Dry Run

Use `--dry-run` to validate the mapping pipeline without sending data. The
script will look up meeting and user info, build the envelope, and print it,
but skip the HTTP POST.
