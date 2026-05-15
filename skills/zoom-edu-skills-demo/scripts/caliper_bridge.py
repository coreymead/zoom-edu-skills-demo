#!/usr/bin/env python3
"""
Zoom-to-Caliper Bridge: Looks up Zoom meeting/user info, maps to a 1EdTech
Caliper v1p2 SessionEvent envelope, and sends it to a Caliper endpoint.

Usage:
    python scripts/caliper_bridge.py \
        --meeting-id 97212343366 \
        --user-id PPOMeM9jRi-KwVgcHIGi3A \
        --action LoggedIn \
        --caliper-endpoint https://example.unizin.org/caliper \
        --caliper-api-key YOUR_API_KEY \
        [--lms-id lms_user_12345] \
        [--sis-id sis_student_67890] \
        [--dry-run]
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import urllib.error
import urllib.request


SYNORA_ROOT = os.environ.get("SYNORA_ROOT", "/home/tmp")
sys.path.insert(0, os.path.join(SYNORA_ROOT, "skills", "system", "search"))

SEARCH_IMPORT_ERROR = None
try:
    from scripts.contact_utils import SearchContactResponse
    from scripts.meeting_utils import MeetingSearchResponse
except ImportError as exc:  # pragma: no cover - depends on external runtime
    SearchContactResponse = None
    MeetingSearchResponse = None
    SEARCH_IMPORT_ERROR = exc


def parse_args():
    parser = argparse.ArgumentParser(
        description="Map a Zoom meeting event to a Caliper v1p2 SessionEvent and send to Unizin."
    )
    parser.add_argument("--meeting-id", required=True, help="Zoom meeting ID")
    parser.add_argument("--user-id", required=True, help="Zoom user ID of the participant")
    parser.add_argument(
        "--action",
        default="LoggedIn",
        help="Caliper action (e.g. LoggedIn, LoggedOut). Default: LoggedIn",
    )
    parser.add_argument(
        "--caliper-endpoint",
        required=True,
        help="Unizin Caliper endpoint URL",
    )
    parser.add_argument(
        "--caliper-api-key",
        required=True,
        help="Bearer token / API key for the Caliper endpoint",
    )
    parser.add_argument("--lms-id", default=None, help="Optional LMS system identifier for the user")
    parser.add_argument("--sis-id", default=None, help="Optional SIS system identifier for the user")
    parser.add_argument("--dry-run", action="store_true", help="Validate mapping without sending")
    return parser.parse_args()


def require_search_runtime():
    if SEARCH_IMPORT_ERROR is not None:
        print(
            "[ERROR] The Zoom search models are unavailable. This skill expects the "
            "Synora/Zoom search runtime under $SYNORA_ROOT.",
            file=sys.stderr,
        )
        print(f"[ERROR] Import detail: {SEARCH_IMPORT_ERROR}", file=sys.stderr)
        sys.exit(1)

    if "search_meeting" not in globals() or "search_contact" not in globals():
        print(
            "[ERROR] Builtin functions 'search_meeting' and 'search_contact' are not "
            "available in this runtime.",
            file=sys.stderr,
        )
        sys.exit(1)


async def lookup_meeting(meeting_id: str):
    """Fetch meeting details via search_meeting builtin."""
    require_search_runtime()
    raw = await search_meeting(meeting_id=[meeting_id])
    response = MeetingSearchResponse(**raw)
    if not response.result:
        print(f"[ERROR] No meeting found for meeting_id={meeting_id}")
        sys.exit(1)
    return response.result[0]


async def lookup_user(user_id: str):
    """Fetch user details via search_contact builtin."""
    require_search_runtime()
    raw = await search_contact(ids=[user_id])
    response = SearchContactResponse(**raw)
    if not response.result or not response.result[0].contact:
        print(f"[ERROR] No contact found for user_id={user_id}")
        sys.exit(1)
    return response.result[0].contact[0]


def build_caliper_envelope(meeting, contact, args):
    """Build a Caliper v1p2 EventEnvelope with a SessionEvent."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    event_time = now_iso
    if meeting.meeting_start_time:
        event_time = datetime.fromtimestamp(
            meeting.meeting_start_time / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    user_info = contact.user_info
    actor_name = user_info.display_name or user_info.full_name or "Unknown User"
    actor_id = f"https://zoom.com/users/{user_info.user_id}"

    other_identifiers = []
    if args.lms_id:
        other_identifiers.append(
            {"type": "SystemIdentifier", "identifier": args.lms_id, "source": "LMS"}
        )
    if args.sis_id:
        other_identifiers.append(
            {"type": "SystemIdentifier", "identifier": args.sis_id, "source": "SIS"}
        )

    meeting_url = f"https://zoom.us/meeting/{args.meeting_id}"
    meeting_topic = meeting.meeting_topic or "Zoom Meeting"

    session_event_id = f"urn:uuid:{uuid.uuid4()}"
    session_event = {
        "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
        "id": session_event_id,
        "type": "SessionEvent",
        "profile": "SessionProfile",
        "actor": {
            "id": actor_id,
            "type": "Person",
            "name": actor_name,
        },
        "action": args.action,
        "object": {
            "id": meeting_url,
            "type": "SoftwareApplication",
            "name": meeting_topic,
            "version": "v5.0",
        },
        "eventTime": event_time,
        "edApp": {
            "id": "https://zoom.com",
            "type": "SoftwareApplication",
        },
        "session": {
            "id": meeting_url,
            "type": "Session",
            "user": actor_id,
            "dateCreated": event_time,
            "startedAtTime": event_time,
        },
    }

    if other_identifiers:
        session_event["actor"]["otherIdentifiers"] = other_identifiers

    envelope_id = f"urn:uuid:{uuid.uuid4()}"
    return {
        "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
        "id": envelope_id,
        "type": "EventEnvelope",
        "dataVersion": "http://purl.imsglobal.org/ctx/caliper/v1p2",
        "sendTime": now_iso,
        "sensor": "https://zoom.com/caliper-sensor",
        "data": [session_event],
    }


def send_to_caliper(envelope, endpoint, api_key, dry_run=False):
    """POST the Caliper envelope to the target endpoint."""
    payload = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")

    if dry_run:
        print("[DRY RUN] Would POST to:", endpoint)
        print("[DRY RUN] Payload:")
        print(payload.decode("utf-8"))
        print("[DRY RUN] Validated successfully - no data sent.")
        return None

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            print(f"Caliper endpoint responded with status {status}")
            try:
                result = json.loads(body)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return result
            except json.JSONDecodeError:
                print("Response body:", body)
                return body
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8") if exc.fp else ""
        print(f"[ERROR] HTTP {exc.code}: {exc.reason}")
        print(f"[ERROR] Response: {error_body}")
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"[ERROR] Connection failed: {exc.reason}")
        sys.exit(1)


async def async_main(args):
    print(f"Looking up meeting {args.meeting_id} ...")
    meeting = await lookup_meeting(args.meeting_id)
    print(f"  Meeting topic: {meeting.meeting_topic or '(Untitled)'}")

    print(f"Looking up user {args.user_id} ...")
    contact = await lookup_user(args.user_id)
    user_info = contact.user_info
    print(
        f"  User: {user_info.display_name or user_info.full_name or 'Unknown'} "
        f"({user_info.email or 'no email'})"
    )

    print("Building Caliper v1p2 SessionEvent envelope ...")
    envelope = build_caliper_envelope(meeting, contact, args)

    print("Sending to Caliper endpoint ...")
    result = send_to_caliper(
        envelope,
        args.caliper_endpoint,
        args.caliper_api_key,
        dry_run=args.dry_run,
    )

    if result and not args.dry_run:
        accepted = result.get("accepted_events", [])
        print(f"\nSuccess: {len(accepted)} event(s) accepted by Caliper endpoint.")
    elif not args.dry_run:
        print("\nCaliper endpoint returned a non-JSON or unexpected response.")

    return envelope


def main():
    args = parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
