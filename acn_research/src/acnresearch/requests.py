"""Prefix-available user requests; no delivered-energy or departure fallback."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math


def timestamp(value):
    if isinstance(value, datetime):
        t = value
    elif 'GMT' in value or ',' in value:
        t = parsedate_to_datetime(value)
    else:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timestamp must carry timezone')
    return t.astimezone(timezone.utc)


def request_asof(session, when):
    """Latest valid request available by when; reject conflicting same-time edits.

    modifiedAt is the documented submission time, not a verified controller
    reception time. Missing/invalid timestamps cannot be assumed known at plug-in.
    """
    when = timestamp(when)
    candidates = []
    for entry in session.get('userInputs') or []:
        try:
            modified = timestamp(entry['modifiedAt'])
            energy = float(entry['kWhRequested'])
            departure = timestamp(entry['requestedDeparture'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if modified <= when and math.isfinite(energy) and energy >= 0:
            candidates.append((modified, energy, departure))
    if not candidates:
        return None
    latest = max(t for t, _, _ in candidates)
    values = {(e, d) for t, e, d in candidates if t == latest}
    if len(values) != 1:
        raise ValueError('Conflicting requests at the same modifiedAt')
    energy, departure = values.pop()
    return {'kwh_requested': energy, 'requested_departure': departure,
            'modified_at': latest}


def recording_filename(session_id):
    return session_id.replace('_', '-').replace(' ', 'T').replace(':', '-').replace('.', '-') + '.csv.gz'
