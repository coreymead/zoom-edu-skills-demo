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

Run the wrapper in this folder:

```bash
python scripts/main.py \
  --meeting-id <MEETING_ID> \
  --user-id <USER_ID> \
  --action <ACTION> \
  --caliper-endpoint <ENDPOINT_URL> \
  --caliper-api-key <API_KEY> \
  [--lms-id <LMS_IDENTIFIER>] \
  [--sis-id <SIS_IDENTIFIER>] \
  [--dry-run]
```

This skill delegates to the shared root implementation in `scripts/caliper_bridge.py`.
