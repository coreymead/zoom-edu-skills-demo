---
name: zoom-edu-skills-demo
description: >
  Provide EDU-focused Zoom workflows from a single skill. Use this skill
  whenever the user needs a Zoom attendance report, class roster comparison,
  late or partial attendance flags, or wants to forward Zoom meeting events to
  1EdTech Caliper or Unizin for LMS analytics. This skill can choose any bundled
  tool underneath it, including attendance reporting and Caliper event
  forwarding.
---

# Zoom EDU Skills Demo

Provide multiple EDU-oriented Zoom workflows from one skill entrypoint.

## Bundled Tools

- `scripts/attendance_report.py` for attendance reports from participant exports
- `scripts/caliper_bridge.py` for forwarding Zoom meeting events to Caliper or Unizin

## When to Use

- The user has a Zoom participant export and wants an attendance report.
- A class roster should be compared against Zoom attendance to flag absences.
- The user wants late-arrival or partial-attendance flags.
- A Zoom meeting event must be transformed into a Caliper `SessionEvent`.
- Zoom attendance data needs to be sent to Unizin or another LMS analytics pipeline.

## Tool Selection

### Attendance Report

Use `scripts/attendance_report.py` when the user wants reporting, summaries, or
roster-aware attendance checks.

Typical requests:

- "Generate an attendance report from this Zoom participant CSV."
- "Compare this class roster with the meeting export and tell me who was absent."
- "Flag late students and give me total minutes attended."

Run:

```bash
python $SYNORA_ROOT/skills/customized/zoom-edu-skills-demo/scripts/attendance_report.py \
  --participants-file <PARTICIPANTS_FILE> \
  [--meeting-title "Biology 101"] \
  [--meeting-start "2026-05-15T09:00:00-04:00"] \
  [--meeting-end "2026-05-15T10:15:00-04:00"] \
  [--expected-duration-minutes 75] \
  [--roster-file <ROSTER_FILE>] \
  [--late-threshold-minutes 10] \
  [--minimum-attendance-percent 75] \
  [--output-format markdown|csv|json] \
  [--output-file <REPORT_OUTPUT_PATH>]
```

Accepted participant inputs:

- CSV
- TSV
- JSON

The attendance tool:

- merges reconnect sessions
- calculates total minutes, first join, and last leave
- computes attendance percentage when meeting length is known
- flags `Late`, `Partial`, and `Absent` statuses

### Caliper Bridge

Use `scripts/caliper_bridge.py` when the user wants to forward Zoom meeting
events into Caliper-compatible LMS analytics systems.

Typical requests:

- "Send this Zoom meeting event to Unizin as a Caliper SessionEvent."
- "Map Zoom attendance into Caliper for our LMS analytics pipeline."
- "Generate the Caliper envelope for this participant join event."

Run:

```bash
python $SYNORA_ROOT/skills/customized/zoom-edu-skills-demo/scripts/caliper_bridge.py \
  --meeting-id <MEETING_ID> \
  --user-id <USER_ID> \
  --action <ACTION> \
  --caliper-endpoint <ENDPOINT_URL> \
  --caliper-api-key <API_KEY> \
  [--lms-id <LMS_IDENTIFIER>] \
  [--sis-id <SIS_IDENTIFIER>] \
  [--dry-run]
```

The Caliper tool:

- looks up meeting details via `search_meeting`
- looks up participant details via `search_contact`
- builds a Caliper v1p2 `EventEnvelope` containing a `SessionEvent`
- optionally performs a dry run without sending data

## Evals

- Attendance fixtures live under `evals/attendance/`.
- Combined example prompts live in `evals/evals.json`.
