import asyncio
import json
import logging
import re
from datetime import date, datetime, time, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Malay day names
MALAY_DAYS = {
    0: "ISNIN",
    1: "SELASA",
    2: "RABU",
    3: "KHAMIS",
    4: "JUMAAT",
    5: "SABTU",
    6: "AHAD",
}


def _get_calendar_service():
    """Build Google Calendar API service from credentials."""
    if not settings.GOOGLE_CREDENTIALS_JSON:
        return None

    creds_dict = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def parse_time_string(time_str: str) -> time | None:
    """Parse flexible time input like '11AM', '2PM', '10:30am', '14:00'."""
    s = time_str.strip().upper().replace(" ", "").replace(".", "")

    # Try "11AM", "2PM", "11:30AM"
    m = re.match(r"^(\d{1,2}):?(\d{2})?\s*(AM|PM)?$", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)

        if ampm == "PM" and hour < 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    return None


def format_date_malay(d: date) -> str:
    """Format date as 'SABTU 27/9/2025'."""
    day_name = MALAY_DAYS.get(d.weekday(), "")
    return f"{day_name} {d.strftime('%-d/%-m/%Y')}"


def format_phone_display(phone: str) -> str:
    """Format phone for the broadcast template: '60 19-388 3673'."""
    # Keep the original formatting but prefix with 60
    p = phone.strip().replace("+", "")
    if p.startswith("0"):
        p = "60 " + p[1:]
    elif p.startswith("60"):
        p = "60 " + p[2:]
    return p


def generate_site_visit_message(
    customer_name: str,
    customer_phone: str,
    customer_address: str,
    visit_date: date,
    visit_time: str,
    details: str,
) -> str:
    """Generate the site visit broadcast message template."""
    date_label = format_date_malay(visit_date)
    phone_display = format_phone_display(customer_phone)

    # Determine relative day label
    today = date.today()
    diff = (visit_date - today).days
    if diff == 0:
        day_label = "hari ini"
    elif diff == 1:
        day_label = "esok"
    elif diff == 2:
        day_label = "lusa"
    else:
        day_label = date_label

    msg = (
        f"Site Visit {day_label} ({date_label})\n"
        f"\n"
        f"▶️CLIENT : {customer_name.upper()} {phone_display}\n"
        f"\n"
        f"ADD : {customer_address or 'TBA'}\n"
        f"\n"
        f"DETAILS : {details.upper()}\n"
        f"\n"
        f"TIME : {visit_time.upper()}"
    )
    return msg


async def create_event(
    event_date: date,
    visit_time: str,
    customer_name: str,
    details: str,
    address: str | None = None,
    customer_phone: str | None = None,
) -> str | None:
    """Create a Google Calendar event. Returns event_id or None if not configured."""
    service = _get_calendar_service()
    if not service:
        logger.warning("Google Calendar not configured, skipping event creation")
        return None

    # Parse time for calendar event
    parsed_time = parse_time_string(visit_time)
    if parsed_time:
        start_dt = datetime.combine(event_date, parsed_time).isoformat()
        end_dt = datetime.combine(
            event_date, (datetime.combine(event_date, parsed_time) + timedelta(hours=2)).time()
        ).isoformat()
    else:
        # Fallback to all-day if time can't be parsed
        start_dt = event_date.isoformat()
        end_dt = (event_date + timedelta(days=1)).isoformat()

    description = (
        f"Client: {customer_name}\n"
        f"Phone: {customer_phone or 'N/A'}\n"
        f"Details: {details}\n"
        f"Time: {visit_time}\n"
        f"{'Address: ' + address if address else ''}"
    )

    event_body = {
        "summary": f"🏗 Site Visit — {customer_name} ({details})",
        "description": description,
    }

    if parsed_time:
        event_body["start"] = {"dateTime": start_dt, "timeZone": "Asia/Kuala_Lumpur"}
        event_body["end"] = {"dateTime": end_dt, "timeZone": "Asia/Kuala_Lumpur"}
    else:
        event_body["start"] = {"date": start_dt}
        event_body["end"] = {"date": end_dt}

    event_body["reminders"] = {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 60}],
    }

    if address:
        event_body["location"] = address

    def _create():
        return (
            service.events()
            .insert(calendarId=settings.GOOGLE_CALENDAR_ID, body=event_body)
            .execute()
        )

    event = await asyncio.to_thread(_create)
    logger.info("Created Google Calendar event: %s", event.get("id"))
    return event.get("id")


async def delete_event(event_id: str) -> bool:
    """Delete a Google Calendar event."""
    service = _get_calendar_service()
    if not service:
        return False

    def _delete():
        service.events().delete(
            calendarId=settings.GOOGLE_CALENDAR_ID, eventId=event_id
        ).execute()

    try:
        await asyncio.to_thread(_delete)
        logger.info("Deleted Google Calendar event: %s", event_id)
        return True
    except Exception:
        logger.exception("Failed to delete Google Calendar event: %s", event_id)
        return False


async def list_events_for_date(event_date: date) -> list[dict]:
    """List all events for a given date from Google Calendar."""
    service = _get_calendar_service()
    if not service:
        return []

    start = datetime.combine(event_date, time(0, 0)).isoformat() + "+08:00"
    end = datetime.combine(event_date + timedelta(days=1), time(0, 0)).isoformat() + "+08:00"

    def _list():
        return (
            service.events()
            .list(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

    try:
        result = await asyncio.to_thread(_list)
        return result.get("items", [])
    except Exception:
        logger.exception("Failed to list Google Calendar events")
        return []
