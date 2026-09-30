#!/usr/bin/env python3
"""
Read-only connectors for the phone-to-mac agent.

Each connector lets the agent CHECK something and report what it found — it can never
change or send anything. They're offered to the model only when configured (a URL, a
token) under config["connectors"], so an unconfigured source simply isn't available.

Security: everything a connector returns is UNTRUSTED content — it's your calendar, your
inbox. The agent treats it as data, never as instructions, and marks the conversation
"tainted" once a connector has returned data, so a booby-trapped calendar entry or email
can't quietly trigger an action (see TAINT_CONFIRM in agent.py). Connectors here also
deliberately leave out the noisiest, most injection-prone fields (e.g. event
descriptions): just the facts you'd want read aloud.

Adding one later (email, Slack, meetings) = one entry in _REGISTRY with a tool spec and a
run() that returns a short plain-text summary.
"""

import datetime
import re
import urllib.request

try:
    import zoneinfo
except ImportError:  # Python < 3.9; the Mac ships 3.9+
    zoneinfo = None

MAX_FETCH = 8_000_000  # cap a fetched calendar so a huge file can't exhaust memory


# --- shared helpers ---------------------------------------------------------
def _fetch(url, timeout=15, cap=MAX_FETCH):
    """GET an http(s) URL and return the body (bytes). Rejects any other scheme."""
    if not isinstance(url, str) or not re.match(r"^https?://", url, re.IGNORECASE):
        raise ValueError("must be an http(s) URL")
    req = urllib.request.Request(url, headers={"User-Agent": "phone-to-mac/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (scheme checked above)
        return r.read(cap + 1)[:cap]


def _tz(config, ccfg):
    """The user's timezone, from the connector, then config['location'], then the system."""
    name = (ccfg or {}).get("timezone") or ((config.get("location") or {}).get("timezone"))
    if name and zoneinfo:
        try:
            return zoneinfo.ZoneInfo(name)
        except Exception:
            pass
    return datetime.datetime.now().astimezone().tzinfo


# --- calendar (read-only, from a secret iCal/ICS URL) -----------------------
CAL_RANGES = ["today", "tomorrow", "week"]


def _calendar_tool(ccfg):
    return {
        "name": "check_calendar",
        "description": (
            "Read the user's own calendar (READ-ONLY) and list their events. Use it when "
            "they ask what's on, their schedule, their next meeting, or what's coming up. "
            "It cannot add, move or delete anything."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "enum": CAL_RANGES,
                    "description": "today, tomorrow, or the next 7 days (week).",
                }
            },
            "required": ["range"],
            "additionalProperties": False,
        },
    }


def _range_dates(rng, tz):
    today = datetime.datetime.now(tz).date()
    if rng == "tomorrow":
        start, days, label = today + datetime.timedelta(days=1), 1, "tomorrow"
    elif rng == "week":
        start, days, label = today, 7, "the next 7 days"
    else:
        start, days, label = today, 1, "today"
    s = datetime.datetime.combine(start, datetime.time.min, tz)
    e = s + datetime.timedelta(days=days)
    return s, e, label


def _event_key(dt, tz):
    """A comparable UTC instant for either an all-day date or a timed datetime."""
    if isinstance(dt, datetime.datetime):
        d = dt if dt.tzinfo else dt.replace(tzinfo=tz)
        return d.astimezone(datetime.timezone.utc)
    return datetime.datetime.combine(dt, datetime.time.min, tz).astimezone(datetime.timezone.utc)


def _clean(text):
    """One line, no control characters — event titles come from an untrusted source."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _format_events(events, label, tz):
    rows = []
    for e in events:
        ds = e.get("DTSTART")
        if ds is None:
            continue
        start = ds.dt
        summary = _clean(e.get("SUMMARY")) or "(no title)"
        loc = _clean(e.get("LOCATION"))
        if isinstance(start, datetime.datetime):
            local = (start if start.tzinfo else start.replace(tzinfo=tz)).astimezone(tz)
            when = local.strftime("%H:%M")
        else:
            when = "all day"
        rows.append((_event_key(start, tz), f"{when} {summary}" + (f" ({loc})" if loc else "")))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return True, f"Nothing on the calendar {label}."
    shown = rows[:12]
    more = "" if len(rows) <= 12 else f" (+{len(rows) - 12} more)"
    return True, f"Calendar for {label}: " + "; ".join(r[1] for r in shown) + more + "."


def _calendar_run(config, ccfg, inp):
    import icalendar
    import recurring_ical_events

    url = ccfg.get("ics_url")
    if not url:
        return False, "no calendar ics_url is set"
    rng = inp.get("range") if inp.get("range") in CAL_RANGES else "today"
    tz = _tz(config, ccfg)
    data = _fetch(url)
    cal = icalendar.Calendar.from_ical(data)
    start, end, label = _range_dates(rng, tz)
    events = recurring_ical_events.of(cal).between(start, end)
    return _format_events(events, label, tz)


# --- registry ---------------------------------------------------------------
_REGISTRY = {
    "calendar": {"tool_name": "check_calendar", "tool": _calendar_tool, "run": _calendar_run},
}

# tool name (what the model calls) -> connector key (what config uses)
TOOL_NAMES = {spec["tool_name"]: key for key, spec in _REGISTRY.items()}


def configured(config):
    """The connector keys that are set up (have a non-empty config block)."""
    return {k: v for k, v in (config.get("connectors") or {}).items() if k in _REGISTRY and v}


def tools(config):
    """Tool specs to offer the model, one per configured connector."""
    return [_REGISTRY[k]["tool"](v) for k, v in configured(config).items()]


def run(config, tool_name, inp):
    """Run a connector tool by its model-facing name. Returns (ok, short text). Never raises."""
    key = TOOL_NAMES.get(tool_name)
    if not key:
        return False, f"unknown connector tool: {tool_name}"
    ccfg = (config.get("connectors") or {}).get(key)
    if not ccfg:
        return False, f"{key} isn't set up"
    try:
        return _REGISTRY[key]["run"](config, ccfg, inp or {})
    except ImportError:
        return False, f"the {key} connector needs extra packages (see requirements.txt)"
    except Exception as e:
        return False, f"couldn't read your {key} ({type(e).__name__})"
