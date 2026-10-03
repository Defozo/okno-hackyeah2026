from icalendar import Calendar
from api.contracts import ExportRequest
from api.exports import card_data, render_ics, render_text
import json
from pathlib import Path


def test_ics_uids_survive_selection_change_and_care_includes_transfer():
    scenario = json.loads(Path('data/synthetic/single-parent.json').read_text(encoding='utf-8'))
    events = [
        {'kind': 'work', 'activity_id': 'work', 'date': '2026-10-05', 'start': '2026-10-05T08:15:00+02:00', 'end': '2026-10-05T16:15:00+02:00'},
        {'kind': 'care_transfer', 'activity_id': None, 'need_id': 'private-child', 'resource_id': 'private-caregiver', 'date': '2026-10-05', 'start': '2026-10-05T15:00:00+02:00', 'end': '2026-10-05T15:15:00+02:00'},
    ]
    request = ExportRequest(scenario=scenario, recipient='personal', approved_fields=['schedule'], event_kinds=['work', 'care'])
    full = card_data(request, {}, {'schedule': events})
    first = Calendar.from_ical(render_ics(full, 'same-plan')).walk('VEVENT')
    request.event_kinds = ['work']
    partial = card_data(request, {}, {'schedule': events})
    second = Calendar.from_ical(render_ics(partial, 'same-plan')).walk('VEVENT')
    assert len(first) == 2 and len(second) == 1
    assert str(first[0]['uid']) == str(second[0]['uid'])
    text = render_text(full)
    assert 'Praca 08:15 - 16:15' in text
    assert 'Przekazanie opieki 15:00 - 15:15' in text
    assert 'private-child' not in text and 'private-caregiver' not in text


def test_calendar_uses_portable_utc_instants_across_warsaw_dst():
    card = {'version': '2', 'status': 'proposal', 'notice': 'Propozycja', 'schedule': [
        {'date': '2026-10-24', 'start': '2026-10-24T08:00:00+02:00', 'end': '2026-10-24T16:00:00+02:00', 'kind': 'work', 'event_key': 'before-dst'},
        {'date': '2026-10-26', 'start': '2026-10-26T08:00:00+01:00', 'end': '2026-10-26T16:00:00+01:00', 'kind': 'work', 'event_key': 'after-dst'}]}
    data = render_ics(card, 'saved-plan')
    assert b'DTSTART:20261024T060000Z' in data
    assert b'DTSTART:20261026T070000Z' in data
    assert b'TZID=' not in data
    assert len(Calendar.from_ical(data).walk('VEVENT')) == 2
