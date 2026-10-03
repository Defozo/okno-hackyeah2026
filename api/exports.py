"""Recipient cards are constructed from a positive allowlist. No private names leak."""
import hashlib
import hmac
import html
import json
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from icalendar import Calendar, Event
from api.settings import settings

ALLOWED = {
    'employer': {'schedule', 'period', 'paid_minutes', 'flexibility', 'trial_period'},
    'caregiver': {'schedule', 'period', 'handoffs', 'trial_period'},
    'advisor': {'schedule', 'period', 'paid_minutes', 'cost', 'barriers', 'actions', 'handoffs', 'trial_period'},
    'personal': {'schedule', 'period', 'paid_minutes', 'cost', 'barriers', 'actions', 'handoffs', 'trial_period'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def card_data(request, result, alternative, status='proposal', trial=None):
    fields = set(request.approved_fields)
    if fields - ALLOWED[request.recipient]:
        raise HTTPException(422, 'Wybrano pole niedozwolone dla tego odbiorcy.')
    scenario = request.scenario.model_dump(mode='json')
    source_schedule = (alternative or result.get('baseline', {})).get('schedule', [])
    if isinstance(source_schedule, dict):
        source_schedule = source_schedule.get('activities', source_schedule.get('events', []))
    public_schedule = []
    occurrences = {}
    for entry in source_schedule:
        kind = entry.get('kind', 'work')
        selection_kind = 'care' if kind in ('handoff', 'care_transfer') else kind
        if selection_kind not in request.event_kinds:
            continue
        if request.recipient == 'employer' and kind != 'work':
            continue
        public = {k: entry[k] for k in ('date', 'start', 'end', 'paid_minutes', 'kind') if k in entry}
        identity = {k: entry.get(k) for k in ('activity_id', 'date', 'kind', 'leg_id', 'resource_id', 'need_id', 'arrangement_id', 'handoff_index', 'journey')}
        key = digest(identity)
        occurrences[key] = occurrences.get(key, 0) + 1
        raw_identity = f"{key}:{occurrences[key]}"
        public['event_key'] = hmac.new(settings.session_secret.encode(), raw_identity.encode(), hashlib.sha256).hexdigest()
        public_schedule.append(public)
    card = {'title': 'Karta uzgodnienia', 'recipient': request.recipient,
            'version': str(request.input_version), 'status': status,
            'notice': 'Propozycja do uzgodnienia. Eksport nie oznacza zgody ani rezerwacji.' if status == 'proposal'
            else 'Potwierdzone według zapisanych ustaleń użytkowniczki.', 'fields': sorted(fields)}
    if 'period' in fields:
        card['period'] = {'start': scenario['start_date'], 'end': scenario['end_date']}
    if 'schedule' in fields:
        card['schedule'] = public_schedule
    metrics = (alternative or {}).get('metrics', {})
    if 'paid_minutes' in fields:
        card['paid_minutes'] = metrics.get('paid_minutes', 0)
    if 'flexibility' in fields:
        card['flexibility'] = 'Godziny wskazane w tabeli. Każda zmiana wymaga ponownego sprawdzenia.'
    if 'trial_period' in fields:
        card['trial_period'] = {'start': (trial or {}).get('start_date', scenario['start_date']),
                               'end': (trial or {}).get('end_date', scenario['end_date']),
                               'recorded': bool(trial)}
    if 'cost' in fields:
        card['cost_grosze'] = metrics.get('cost_grosze')
    if 'barriers' in fields:
        card['barriers'] = [str(x.get('message', x.get('description', 'Warunek wymaga uzupełnienia'))) for x in result.get('conflicts', [])]
    if 'actions' in fields:
        card['actions'] = [str(x.get('title', x.get('description', 'Uzgodnić warunek'))) for x in (alternative or {}).get('actions', [])]
    if 'handoffs' in fields:
        # No dependent IDs or addresses in recipient cards; care events carry only dates/times.
        card['handoffs'] = [{k: e[k] for k in ('date', 'start', 'end') if k in e} for e in source_schedule if e.get('kind') in ('care', 'handoff', 'care_transfer')]
    return card


def render_text(card):
    lines = ['OKNO / Karta uzgodnienia', card['notice'], f"Wersja: {card['version']}"]
    if 'period' in card:
        lines.append(f"Sprawdzony okres: {card['period']['start']} do {card['period']['end']}")
    if 'paid_minutes' in card:
        lines.append(f"Płatny czas pracy: {card['paid_minutes'] / 60:g} h w sprawdzonym okresie")
    for e in card.get('schedule', []):
        start, end = e.get('start', ''), e.get('end', '')
        start = start[11:16] if 'T' in start else start
        end = end[11:16] if 'T' in end else end
        kind = {'work': 'Praca', 'course': 'Kurs', 'care': 'Opieka', 'care_transfer': 'Przekazanie opieki', 'handoff': 'Przekazanie opieki', 'travel': 'Podróż', 'obligation': 'Zajęcia'}.get(e.get('kind'), 'Zdarzenie')
        lines.append(f"{e.get('date', '')}: {kind} {start} - {end}")
    if 'trial_period' in card:
        period = card['trial_period']
        lines.append(f"{'Zapisany' if period['recorded'] else 'Proponowany'} okres próby: {period['start']} do {period['end']}" + ('.' if period['recorded'] else ', do osobnego uzgodnienia.'))
    if 'cost_grosze' in card:
        amount = card['cost_grosze']
        lines.append('Koszt w okresie: ' + ('nieznany' if amount is None else f'{amount / 100:.2f} zł'))
    if 'handoffs' in card:
        lines.append('Opieka i przekazania:')
        for entry in card['handoffs']:
            start, end = entry.get('start', ''), entry.get('end', '')
            lines.append(f"{entry.get('date', '')}: {start[11:16] if 'T' in start else start} - {end[11:16] if 'T' in end else end}")
    for key, label in [('flexibility', 'Elastyczność'), ('barriers', 'Bariery'), ('actions', 'Działania')]:
        if key in card:
            lines.append(label + ': ' + ('; '.join(str(value) for value in card[key]) if isinstance(card[key], list) else str(card[key])))
    lines.append('Pobranych plików ani wydarzeń zaimportowanych do kalendarza nie można zdalnie cofnąć.')
    return '\n'.join(lines)


def render_html(card):
    text = html.escape(render_text(card))
    return '<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Okno: karta uzgodnienia</title><style>body{font:17px/1.65 Arial,sans-serif;color:#173f35;max-width:820px;margin:40px auto;padding:24px}h1{font-size:32px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}@page{size:A4;margin:20mm}</style><main><h1>Okno</h1><pre>' + text + '</pre></main></html>'


def sign_preview(owner, payload_hash, expires):
    body = f'{owner}:{payload_hash}:{expires}'
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f'{expires}.{signature}'


def preview_token(owner, request, card):
    expires = int(time.time()) + 900
    content_hash = digest({'scenario': request.scenario.model_dump(mode='json'), 'card': card, 'alternative_id': request.alternative_id})
    return sign_preview(owner, content_hash, expires), expires


def verify_preview(owner, request, card):
    try:
        expires = int((request.preview_id or '').split('.')[0])
    except ValueError:
        raise HTTPException(409, 'Najpierw odśwież podgląd odbiorcy.')
    content_hash = digest({'scenario': request.scenario.model_dump(mode='json'), 'card': card, 'alternative_id': request.alternative_id})
    if expires < time.time() or not hmac.compare_digest(request.preview_id or '', sign_preview(owner, content_hash, expires)):
        raise HTTPException(409, 'Dane lub zakres zmieniły się. Odśwież podgląd odbiorcy.')


async def render_pdf(card):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            page = await browser.new_page(java_script_enabled=False)
            await page.route('**/*', lambda route: route.abort())
            await page.set_content(render_html(card), wait_until='domcontentloaded')
            return await page.pdf(format='A4', print_background=True)
        finally:
            await browser.close()


def render_ics(card, scope):
    calendar = Calendar()
    calendar.add('prodid', '-//Okno//Uzgodniony plan//PL')
    calendar.add('version', '2.0')
    calendar.add('method', 'PUBLISH')
    for index, entry in enumerate(card.get('schedule', [])):
        if not entry.get('date') or not entry.get('start') or not entry.get('end'):
            continue
        def moment(raw):
            value = raw if 'T' in raw else f"{entry['date']}T{raw}"
            dt = datetime.fromisoformat(value)
            return dt.replace(tzinfo=ZoneInfo('Europe/Warsaw')) if dt.tzinfo is None else dt
        start, end = moment(entry['start']), moment(entry['end'])
        if end <= start:
            from datetime import timedelta
            end += timedelta(days=1)
        event = Event()
        event.add('uid', digest({'scope': scope, 'event': entry['event_key']}) + '@okno.local')
        event.add('dtstamp', datetime.now(timezone.utc))
        # UTC instants preserve Warsaw DST offsets without inventing a TZID such
        # as UTC+02:00 that calendar clients cannot resolve without VTIMEZONE.
        event.add('dtstart', start.astimezone(timezone.utc))
        event.add('dtend', end.astimezone(timezone.utc))
        event.add('sequence', int(card['version']) if card['version'].isdigit() else 1)
        label = {'work': 'Praca', 'course': 'Kurs', 'care': 'Opieka', 'care_transfer': 'Przekazanie opieki', 'handoff': 'Przekazanie opieki', 'travel': 'Podróż', 'obligation': 'Zajęcia'}.get(entry.get('kind'), 'Zdarzenie')
        event.add('summary', label + (': propozycja' if card['status'] == 'proposal' else ' według zapisanych ustaleń'))
        event.add('description', card['notice'])
        calendar.add_component(event)
    return calendar.to_ical()
