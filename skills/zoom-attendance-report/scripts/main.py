#!/usr/bin/env python3
"""
Generate an attendance report from a Zoom participant list.

Examples:
    python scripts/main.py \
        --participants-file participants.csv \
        --meeting-title "Biology 101" \
        --meeting-start "2026-05-15T09:00:00-04:00" \
        --meeting-end "2026-05-15T10:15:00-04:00"

    python scripts/main.py \
        --participants-file participants.json \
        --roster-file roster.csv \
        --expected-duration-minutes 75 \
        --output-format csv \
        --output-file attendance_report.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


FIELD_ALIASES = {
    "name": (
        "name",
        "participant_name",
        "display_name",
        "user_name",
        "full_name",
        "original_name",
        "name_original_name",
    ),
    "email": (
        "email",
        "user_email",
        "participant_email",
        "email_address",
    ),
    "user_id": (
        "user_id",
        "participant_id",
        "zoom_user_id",
        "id",
    ),
    "join_time": (
        "join_time",
        "join",
        "joined_at",
        "join_timestamp",
        "join_date_time",
        "start_time",
    ),
    "leave_time": (
        "leave_time",
        "leave",
        "left_at",
        "leave_timestamp",
        "leave_date_time",
        "end_time",
    ),
    "duration_minutes": (
        "duration_minutes",
        "duration_in_minutes",
        "duration_min",
        "duration_mins",
        "duration",
    ),
}


TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M %p",
    "%b %d, %Y %I:%M:%S %p",
    "%b %d, %Y %I:%M %p",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an attendance report from a Zoom participant list."
    )
    parser.add_argument(
        "--participants-file",
        required=True,
        help="CSV, TSV, or JSON file containing Zoom participant rows.",
    )
    parser.add_argument(
        "--meeting-title",
        default="Zoom Meeting",
        help="Title shown in the report. Default: Zoom Meeting",
    )
    parser.add_argument(
        "--meeting-start",
        help="Meeting start time used to flag late arrivals.",
    )
    parser.add_argument(
        "--meeting-end",
        help="Meeting end time used to derive expected duration.",
    )
    parser.add_argument(
        "--expected-duration-minutes",
        type=float,
        help="Expected meeting length in minutes when meeting end is not provided.",
    )
    parser.add_argument(
        "--roster-file",
        help="Optional class roster file to flag absent participants.",
    )
    parser.add_argument(
        "--late-threshold-minutes",
        type=float,
        default=10.0,
        help="Minutes after meeting start that counts as late. Default: 10",
    )
    parser.add_argument(
        "--minimum-attendance-percent",
        type=float,
        default=75.0,
        help="Attendance percentage below which a participant is flagged partial. Default: 75",
    )
    parser.add_argument(
        "--timezone",
        default="UTC",
        help="Timezone for naive timestamps and rendered times. Default: UTC",
    )
    parser.add_argument(
        "--output-format",
        choices=("markdown", "csv", "json"),
        default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--output-file",
        help="Optional path to write the report instead of printing it to stdout.",
    )
    return parser.parse_args()


def normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized_key = normalize_key(str(key))
        normalized[normalized_key] = value.strip() if isinstance(value, str) else value
    return normalized


def pick_value(row: dict[str, Any], field_name: str) -> Any:
    for alias in FIELD_ALIASES[field_name]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def parse_duration_minutes(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)

    if ":" in text and re.fullmatch(r"[0-9:]+", text):
        parts = [int(part) for part in text.split(":")]
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = parts
        else:
            return None
        total_seconds = (hours * 3600) + (minutes * 60) + seconds
        return total_seconds / 60.0

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)",
        text,
    )
    if matches:
        total_minutes = 0.0
        for amount, unit in matches:
            number = float(amount)
            if unit.startswith("h"):
                total_minutes += number * 60
            elif unit.startswith("m"):
                total_minutes += number
            else:
                total_minutes += number / 60
        return total_minutes

    number_match = re.search(r"\d+(?:\.\d+)?", text)
    if number_match:
        return float(number_match.group(0))
    return None


def parse_timestamp(value: Any, default_tz: ZoneInfo) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt.astimezone(default_tz)

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(default_tz)

    text = str(value).strip()
    if not text:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", text):
        return parse_timestamp(float(text), default_tz)

    iso_candidate = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt.astimezone(default_tz)
    except ValueError:
        pass

    for fmt in TIMESTAMP_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            dt = dt.replace(tzinfo=default_tz)
            return dt.astimezone(default_tz)
        except ValueError:
            continue

    return None


def load_structured_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("participants"), list):
                data = data["participants"]
            elif isinstance(data.get("result"), list):
                data = data["result"]
        if not isinstance(data, list):
            raise ValueError("JSON input must be a list or an object with a 'participants' list.")
        return [dict(item) for item in data if isinstance(item, dict)]

    delimiter = "\t" if suffix == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        if suffix == ".csv":
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("Delimited input is missing a header row.")
        return [dict(row) for row in reader]


def load_roster_entries(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".txt":
        entries: list[dict[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if "@" in cleaned:
                entries.append({"email": cleaned})
            else:
                entries.append({"name": cleaned})
        return entries

    entries: list[dict[str, str]] = []
    for raw_row in load_structured_rows(path):
        row = normalize_row(raw_row)
        name = pick_value(row, "name")
        email = pick_value(row, "email")
        user_id = pick_value(row, "user_id")
        if name or email or user_id:
            entries.append(
                {
                    "name": str(name or "").strip(),
                    "email": str(email or "").strip(),
                    "user_id": str(user_id or "").strip(),
                }
            )
    return entries


def participant_key(name: str, email: str, user_id: str) -> str | None:
    if email:
        return f"email:{email.strip().lower()}"
    if user_id:
        return f"user:{user_id.strip()}"
    if name:
        return f"name:{name.strip().lower()}"
    return None


def display_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M %Z")


def escape_markdown_cell(value: str) -> str:
    if not value:
        return "—"
    return value.replace("|", "\\|")


def choose_text(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming
    return incoming if len(incoming) > len(current) else current


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda pair: pair[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


@dataclass
class ParticipantAggregate:
    name: str = ""
    email: str = ""
    user_id: str = ""
    sessions: int = 0
    intervals: list[tuple[datetime, datetime]] = field(default_factory=list)
    duration_only_minutes: float = 0.0

    def add_identity(self, name: str, email: str, user_id: str) -> None:
        self.name = choose_text(self.name, name)
        self.email = choose_text(self.email, email)
        self.user_id = choose_text(self.user_id, user_id)

    def add_interval(self, start: datetime, end: datetime) -> None:
        self.sessions += 1
        self.intervals.append((start, end))

    def add_duration_only(self, minutes: float) -> None:
        self.sessions += 1
        self.duration_only_minutes += max(minutes, 0.0)

    def merged_minutes(self) -> float:
        total_minutes = self.duration_only_minutes
        for start, end in merge_intervals(self.intervals):
            total_minutes += (end - start).total_seconds() / 60.0
        return round(total_minutes, 2)

    def first_join(self) -> datetime | None:
        if not self.intervals:
            return None
        return min(start for start, _ in self.intervals)

    def last_leave(self) -> datetime | None:
        if not self.intervals:
            return None
        return max(end for _, end in self.intervals)


@dataclass
class ReportRow:
    participant: str
    email: str
    user_id: str
    sessions: int
    first_join: str
    last_leave: str
    total_minutes: float
    attendance_percent: float | None
    late_by_minutes: float | None
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "participant": self.participant,
            "email": self.email,
            "user_id": self.user_id,
            "sessions": self.sessions,
            "first_join": self.first_join,
            "last_leave": self.last_leave,
            "total_minutes": self.total_minutes,
            "attendance_percent": self.attendance_percent,
            "late_by_minutes": self.late_by_minutes,
            "status": self.status,
        }


def build_aggregates(
    participants_path: Path,
    default_tz: ZoneInfo,
    warnings: list[str],
) -> dict[str, ParticipantAggregate]:
    aggregates: dict[str, ParticipantAggregate] = {}

    for row_number, raw_row in enumerate(load_structured_rows(participants_path), start=2):
        row = normalize_row(raw_row)
        name = str(pick_value(row, "name") or "").strip()
        email = str(pick_value(row, "email") or "").strip()
        user_id = str(pick_value(row, "user_id") or "").strip()
        join_time = parse_timestamp(pick_value(row, "join_time"), default_tz)
        leave_time = parse_timestamp(pick_value(row, "leave_time"), default_tz)
        duration_minutes = parse_duration_minutes(pick_value(row, "duration_minutes"))

        if join_time and not leave_time and duration_minutes is not None:
            leave_time = join_time + timedelta(minutes=duration_minutes)
        if leave_time and not join_time and duration_minutes is not None:
            join_time = leave_time - timedelta(minutes=duration_minutes)

        key = participant_key(name, email, user_id)
        if key is None:
            warnings.append(
                f"Skipping row {row_number}: missing participant identity fields such as name, email, or user_id."
            )
            continue

        aggregate = aggregates.setdefault(key, ParticipantAggregate())
        aggregate.add_identity(name, email, user_id)

        if join_time and leave_time:
            if leave_time < join_time:
                warnings.append(
                    f"Skipping row {row_number}: leave_time is earlier than join_time for '{name or email or user_id}'."
                )
                continue
            aggregate.add_interval(join_time, leave_time)
            continue

        if duration_minutes is not None:
            aggregate.add_duration_only(duration_minutes)
            continue

        warnings.append(
            f"Skipping row {row_number}: no usable timing fields found for '{name or email or user_id}'."
        )

    return aggregates


def apply_roster(
    aggregates: dict[str, ParticipantAggregate],
    roster_path: Path,
) -> None:
    for entry in load_roster_entries(roster_path):
        name = entry.get("name", "").strip()
        email = entry.get("email", "").strip()
        user_id = entry.get("user_id", "").strip()
        key = participant_key(name, email, user_id)
        if key is None:
            continue
        aggregate = aggregates.setdefault(key, ParticipantAggregate())
        aggregate.add_identity(name, email, user_id)


def build_status(
    aggregate: ParticipantAggregate,
    meeting_start: datetime | None,
    late_threshold_minutes: float,
    attendance_percent: float | None,
    minimum_attendance_percent: float,
) -> tuple[str, float | None]:
    total_minutes = aggregate.merged_minutes()
    if aggregate.sessions == 0 and total_minutes == 0:
        return "Absent", None

    late_by_minutes: float | None = None
    if meeting_start and aggregate.first_join():
        late_by_minutes = round(
            max(
                0.0,
                (aggregate.first_join() - meeting_start).total_seconds() / 60.0,
            ),
            2,
        )

    flags: list[str] = []
    if late_by_minutes is not None and late_by_minutes >= late_threshold_minutes:
        flags.append("Late")
    if (
        attendance_percent is not None
        and attendance_percent < minimum_attendance_percent
    ):
        flags.append("Partial")

    return (", ".join(flags) if flags else "Present"), late_by_minutes


def build_report_rows(
    aggregates: dict[str, ParticipantAggregate],
    meeting_start: datetime | None,
    expected_duration_minutes: float | None,
    late_threshold_minutes: float,
    minimum_attendance_percent: float,
) -> list[ReportRow]:
    report_rows: list[ReportRow] = []

    for aggregate in sorted(
        aggregates.values(),
        key=lambda item: ((item.name or item.email or item.user_id).lower()),
    ):
        total_minutes = aggregate.merged_minutes()
        attendance_percent = None
        if expected_duration_minutes and expected_duration_minutes > 0:
            attendance_percent = round(
                min(100.0, (total_minutes / expected_duration_minutes) * 100.0),
                2,
            )

        status, late_by_minutes = build_status(
            aggregate,
            meeting_start,
            late_threshold_minutes,
            attendance_percent,
            minimum_attendance_percent,
        )

        report_rows.append(
            ReportRow(
                participant=aggregate.name or aggregate.email or aggregate.user_id or "Unknown Participant",
                email=aggregate.email,
                user_id=aggregate.user_id,
                sessions=aggregate.sessions,
                first_join=display_timestamp(aggregate.first_join()),
                last_leave=display_timestamp(aggregate.last_leave()),
                total_minutes=total_minutes,
                attendance_percent=attendance_percent,
                late_by_minutes=late_by_minutes,
                status=status,
            )
        )

    return report_rows


def build_summary(rows: list[ReportRow]) -> dict[str, Any]:
    attended_any_count = sum(1 for row in rows if row.status != "Absent")
    late_count = sum(1 for row in rows if "Late" in row.status)
    partial_count = sum(1 for row in rows if "Partial" in row.status)
    absent_count = sum(1 for row in rows if row.status == "Absent")
    fully_present_count = sum(1 for row in rows if row.status == "Present")

    return {
        "participants_in_report": len(rows),
        "attended_any": attended_any_count,
        "fully_present": fully_present_count,
        "late_flagged": late_count,
        "partial_flagged": partial_count,
        "absent": absent_count,
    }


def render_markdown(
    rows: list[ReportRow],
    summary: dict[str, Any],
    meeting_title: str,
    meeting_start: datetime | None,
    expected_duration_minutes: float | None,
) -> str:
    lines = [f"# Attendance Report: {meeting_title}", ""]
    lines.append(f"- Participants in report: {summary['participants_in_report']}")
    lines.append(f"- Attended at least once: {summary['attended_any']}")
    lines.append(f"- Fully present: {summary['fully_present']}")
    lines.append(f"- Late flagged: {summary['late_flagged']}")
    lines.append(f"- Partial flagged: {summary['partial_flagged']}")
    lines.append(f"- Absent: {summary['absent']}")
    if meeting_start:
        lines.append(f"- Meeting start: {display_timestamp(meeting_start)}")
    if expected_duration_minutes:
        lines.append(f"- Expected duration: {round(expected_duration_minutes, 2)} minutes")
    lines.extend(
        [
            "",
            "| Participant | Email | Sessions | First Join | Last Leave | Minutes | Attendance % | Late By (min) | Status |",
            "|---|---|---:|---|---|---:|---:|---:|---|",
        ]
    )

    for row in rows:
        attendance_percent = "" if row.attendance_percent is None else f"{row.attendance_percent:.2f}"
        late_by_minutes = "" if row.late_by_minutes is None else f"{row.late_by_minutes:.2f}"
        lines.append(
            "| {participant} | {email} | {sessions} | {first_join} | {last_leave} | {minutes:.2f} | {attendance_percent} | {late_by_minutes} | {status} |".format(
                participant=escape_markdown_cell(row.participant),
                email=escape_markdown_cell(row.email),
                sessions=row.sessions,
                first_join=escape_markdown_cell(row.first_join),
                last_leave=escape_markdown_cell(row.last_leave),
                minutes=row.total_minutes,
                attendance_percent=attendance_percent or "—",
                late_by_minutes=late_by_minutes or "—",
                status=escape_markdown_cell(row.status),
            )
        )

    return "\n".join(lines)


def render_csv(rows: list[ReportRow]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "participant",
            "email",
            "user_id",
            "sessions",
            "first_join",
            "last_leave",
            "total_minutes",
            "attendance_percent",
            "late_by_minutes",
            "status",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row.as_dict())
    return output.getvalue()


def render_json(
    rows: list[ReportRow],
    summary: dict[str, Any],
    meeting_title: str,
    meeting_start: datetime | None,
    expected_duration_minutes: float | None,
) -> str:
    payload = {
        "meeting_title": meeting_title,
        "meeting_start": display_timestamp(meeting_start),
        "expected_duration_minutes": expected_duration_minutes,
        "summary": summary,
        "participants": [row.as_dict() for row in rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_or_print_report(output_text: str, output_file: str | None) -> None:
    if output_file:
        destination = Path(output_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output_text, encoding="utf-8")
        print(f"Wrote report to {destination}")
        return
    print(output_text)


def main() -> None:
    args = parse_args()

    try:
        default_tz = ZoneInfo(args.timezone)
    except Exception as exc:  # pragma: no cover - zone configuration depends on runtime
        print(f"[ERROR] Invalid timezone '{args.timezone}': {exc}", file=sys.stderr)
        sys.exit(1)

    participants_path = Path(args.participants_file)
    if not participants_path.exists():
        print(f"[ERROR] Participants file not found: {participants_path}", file=sys.stderr)
        sys.exit(1)

    meeting_start = parse_timestamp(args.meeting_start, default_tz) if args.meeting_start else None
    meeting_end = parse_timestamp(args.meeting_end, default_tz) if args.meeting_end else None
    if args.meeting_start and meeting_start is None:
        print(f"[ERROR] Unable to parse meeting start: {args.meeting_start}", file=sys.stderr)
        sys.exit(1)
    if args.meeting_end and meeting_end is None:
        print(f"[ERROR] Unable to parse meeting end: {args.meeting_end}", file=sys.stderr)
        sys.exit(1)
    if meeting_start and meeting_end and meeting_end < meeting_start:
        print("[ERROR] meeting_end cannot be earlier than meeting_start.", file=sys.stderr)
        sys.exit(1)

    expected_duration_minutes = args.expected_duration_minutes
    if expected_duration_minutes is None and meeting_start and meeting_end:
        expected_duration_minutes = round(
            (meeting_end - meeting_start).total_seconds() / 60.0,
            2,
        )

    warnings: list[str] = []
    try:
        aggregates = build_aggregates(participants_path, default_tz, warnings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Failed to load participants file: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.roster_file:
        roster_path = Path(args.roster_file)
        if not roster_path.exists():
            print(f"[ERROR] Roster file not found: {roster_path}", file=sys.stderr)
            sys.exit(1)
        try:
            apply_roster(aggregates, roster_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[ERROR] Failed to load roster file: {exc}", file=sys.stderr)
            sys.exit(1)

    if not aggregates:
        print("[ERROR] No usable participant records were found.", file=sys.stderr)
        sys.exit(1)

    rows = build_report_rows(
        aggregates,
        meeting_start,
        expected_duration_minutes,
        args.late_threshold_minutes,
        args.minimum_attendance_percent,
    )
    summary = build_summary(rows)

    if args.output_format == "markdown":
        output_text = render_markdown(
            rows,
            summary,
            args.meeting_title,
            meeting_start,
            expected_duration_minutes,
        )
    elif args.output_format == "csv":
        output_text = render_csv(rows)
    else:
        output_text = render_json(
            rows,
            summary,
            args.meeting_title,
            meeting_start,
            expected_duration_minutes,
        )

    write_or_print_report(output_text, args.output_file)

    if warnings:
        print("\nWarnings:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)


if __name__ == "__main__":
    main()
