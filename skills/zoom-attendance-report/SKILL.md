---
name: zoom-attendance-report
description: >
  Generate an EDU-friendly attendance report from a Zoom meeting participant
  list. Use this skill whenever the user mentions Zoom attendance, participant
  exports, class attendance, meeting roster comparison, late arrivals, or wants
  a markdown, CSV, or JSON attendance report from Zoom participant data, even
  if they do not explicitly ask for a "skill" or "attendance report".
---

# Zoom Attendance Report

Turn a Zoom meeting participant list into a clean attendance report for classes,
office hours, advising sessions, or other EDU workflows.

## When to Use

- A Zoom participant export needs to become an attendance report.
- The user wants total minutes attended, first join, last leave, or reconnect-aware totals.
- A class roster should be compared against meeting attendance to flag absences.
- The output should be a markdown summary, CSV, or JSON report.

## Examples

- "Take this Zoom participant CSV and make an attendance report for Biology 101."
- "Compare this meeting export with my class roster and tell me who was absent."
- "Generate a CSV attendance report with late students flagged."

## Workflow

1. Collect the required input file: `participants_file`.
2. Optionally collect:
   - `meeting_title`
   - `meeting_start`
   - `meeting_end` or `expected_duration_minutes`
   - `roster_file`
   - `late_threshold_minutes`
   - `minimum_attendance_percent`
   - `output_format`
3. Run the script:

```bash
python $SYNORA_ROOT/skills/customized/zoom-attendance-report/scripts/main.py \
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

## Accepted Inputs

- `participants_file` can be CSV, TSV, or JSON.
- The script auto-detects common field names such as:
  - participant name
  - email
  - user ID
  - join time
  - leave time
  - duration in minutes
- Reconnect rows for the same participant are merged so attendance is not double-counted.

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--participants-file` | Yes | — | Zoom participant export in CSV, TSV, or JSON format |
| `--meeting-title` | No | `Zoom Meeting` | Report title |
| `--meeting-start` | No | — | Meeting start timestamp used to flag late arrivals |
| `--meeting-end` | No | — | Meeting end timestamp used to derive expected duration |
| `--expected-duration-minutes` | No | — | Expected class length when `meeting_end` is not provided |
| `--roster-file` | No | — | Optional roster file to flag absences |
| `--late-threshold-minutes` | No | `10` | Minutes after start that counts as late |
| `--minimum-attendance-percent` | No | `75` | Attendance threshold below which a participant is flagged partial |
| `--timezone` | No | `UTC` | Time zone for naive timestamps and rendered times |
| `--output-format` | No | `markdown` | Report format |
| `--output-file` | No | — | Write the report to a file instead of stdout |

## What the Script Produces

The report includes:

- unique participants
- merged attendance minutes across reconnects
- first join and last leave timestamps
- session count
- attendance percentage when meeting length is known
- late and partial-attendance flags
- optional absences when a roster is supplied

## Notes

- If `meeting_start` is provided, the script flags participants whose first join exceeds the late threshold.
- If `meeting_end` or `expected_duration_minutes` is provided, the script calculates attendance percentages.
- If both a participant list and a roster are provided, participants missing from the meeting are marked `Absent`.
