---
name: zoom-attendance-report
description: >
  Generate an EDU-friendly attendance report from a Zoom meeting participant
  list. Use this skill whenever the user mentions Zoom attendance, participant
  exports, class attendance, meeting roster comparison, late arrivals, or wants
  a markdown, CSV, or JSON attendance report from Zoom participant data.
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

Run the wrapper in this folder:

```bash
python scripts/main.py \
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

This skill delegates to the shared root implementation in `scripts/attendance_report.py`.
