from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from api.database import Plan, Operation, Tombstone, utcnow
from api.exports import digest
from api.settings import settings
from api.calendar_clock import warsaw_today


def find_plan(db, plan_id, owner):
    row = db.get(Plan, plan_id)
    if not row or row.owner != owner:
        raise HTTPException(404, 'Nie znaleziono planu w tej sesji.')
    updated = row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at.tzinfo is None else row.updated_at
    if updated < utcnow() - timedelta(days=settings.retention_days):
        raise HTTPException(410, 'Upłynął okres przechowywania planu.')
    return row


def operation_identity(request, owner, body):
    key = request.headers.get('idempotency-key', '')
    if not 8 <= len(key) <= 128:
        raise HTTPException(422, 'Wymagany jest identyfikator idempotencji.')
    identity = hashlib.sha256(f'{owner}:{key}'.encode()).hexdigest()
    return identity, digest({'method': request.method, 'path': request.url.path, 'body': body})


def prior_operation(db, identity, request_hash):
    op = db.get(Operation, identity)
    if op:
        if op.request_hash != request_hash:
            raise HTTPException(409, 'Identyfikator został użyty dla innych danych.')
        if op.plan_id and db.get(Tombstone, op.plan_id):
            raise HTTPException(410, 'Plan został usunięty. Stare żądanie nie może go przywrócić.')
        return op.response


def record_operation(db, identity, request_hash, owner, response, plan_id=None):
    db.add(Operation(id=identity, request_hash=request_hash, owner=owner, response=response, plan_id=plan_id))


def alternative_for(payload, alternative_id=None):
    selected = alternative_id or payload.get('selected_alternative_id')
    return next((a for a in payload.get('result', {}).get('alternatives', []) if a['id'] == selected), None)


def reset_source_claims(scenario):
    """Backup claims are history; they cannot authorize a restored plan."""
    for collection in ('activities', 'care_resources', 'travel_legs'):
        for entry in scenario.get(collection, []):
            entry.setdefault('source', {})['status'] = 'unknown'
            if collection == 'care_resources':
                entry['confirmed'] = False
                entry['confirmation_valid_to'] = None
    for need in scenario.get('care_needs', []):
        for arrangement in need.get('arrangements', []):
            for handoff in arrangement.get('handoffs', []):
                handoff['confirmed'] = False
                handoff['valid_to'] = None
                handoff.setdefault('source', {})['status'] = 'unknown'


def dependency_fingerprint(scenario, alternative, dependency):
    """Tie consent to only the relevant agreement, dates and chosen assignment."""
    dep_id = dependency['id']
    activity_id = dependency.get('activity_id')
    resource_id = dependency.get('resource_id')
    refs = dependency.get('fields', [])
    activity_ids = {ref.split('.')[1] for ref in refs if ref.startswith('activities.') and len(ref.split('.')) >= 2}
    if activity_id:
        activity_ids.add(activity_id)
    relevant = {'period': [scenario['start_date'], scenario['end_date']],
                'dependency': {k: v for k, v in dependency.items() if k not in ('status', 'confirmation')}}
    if activity_ids:
        relevant['activities'] = [a for a in scenario['activities'] if a['id'] in activity_ids]
    elif 'work' in dep_id or dependency.get('kind') in ('employer', 'work', 'schedule'):
        relevant['activities'] = scenario['activities']
    if resource_id:
        relevant['resources'] = [r for r in scenario['care_resources'] if r['id'] == resource_id]
    elif 'care' in dep_id:
        relevant['resources'] = scenario['care_resources']
    if not activity_id and not resource_id and not refs:
        relevant['scenario'] = scenario
    schedule = alternative.get('schedule', [])
    if isinstance(schedule, list):
        relevant['hours'] = [{k: e.get(k) for k in ('activity_id', 'date', 'start', 'end')} for e in schedule
                             if (e.get('activity_id') in activity_ids and e.get('kind') in ('work', 'course', 'obligation'))
                             or (not activity_id and (not resource_id or e.get('resource_id') == resource_id))]
    # A care change must not invalidate an unrelated employer agreement.
    relevant['proposal'] = dependency.get('proposal')
    return digest(relevant)


def annotate(payload):
    p = deepcopy(payload)
    today = warsaw_today().isoformat()
    for alt in p.get('result', {}).get('alternatives', []):
        all_confirmed = True
        rejected = False
        for dep in alt.get('dependencies', []):
            fingerprint = dependency_fingerprint(p['scenario'], alt, dep)
            matches = [d for d in p.get('decisions', []) if d['dependency_id'] == dep['id'] and d.get('fingerprint') == fingerprint and not d.get('restored')]
            decision = matches[-1] if matches else None
            valid = decision and decision['valid_until'] >= max(today, p['scenario']['end_date'])
            dep['confirmation'] = 'accepted' if valid and decision['decision'] == 'accepted' else 'pending'
            if valid and decision['decision'] == 'rejected':
                dep['confirmation'] = 'rejected'
                rejected = True
            if dep['confirmation'] != 'accepted':
                all_confirmed = False
        mathematically_valid = alt.get('solver_status', p['result'].get('status')) in ('OPTIMAL', 'FEASIBLE') and p['result'].get('data_status') == 'complete'
        alt['status'] = 'rejected' if rejected else 'confirmed' if all_confirmed and mathematically_valid else 'awaiting_confirmation'
        alt['confirmation_label'] = 'Potwierdzone według zapisanych ustaleń' if alt['status'] == 'confirmed' else 'Wymaga uzgodnień'
    selected = alternative_for(p)
    p['status'] = selected['status'] if selected else 'draft'
    if p.get('trial'):
        blocked = not selected or selected['status'] != 'confirmed' or p['trial'].get('scenario_hash') != digest(p['scenario'])
        p['trial']['blocked'] = blocked
        p['trial']['block_reason'] = 'Warunki planu zmieniły się lub ustalenia wygasły. Sprawdź plan ponownie.' if blocked else None
        p['status'] = 'completed' if p['trial'].get('completed') else 'trial'
    p['impact'] = impact(p)
    return p


def impact(payload):
    trial = payload.get('trial')
    outcomes = payload.get('outcomes', [])
    result = {'source': 'self_report', 'observations': len(outcomes), 'actual_worked_minutes': sum(o.get('worked_minutes') or 0 for o in outcomes),
              'synthetic': payload['scenario'].get('data_mode') == 'synthetic',
              'actual_cost_grosz': sum(o.get('cost_grosz') or 0 for o in outcomes),
              'actual_organization_minutes': sum(o.get('organization_minutes') or 0 for o in outcomes),
              'baseline_status': 'baseline_missing', 'normalized_work_change_minutes': None,
              'normalized_cost_change_grosz': None, 'normalized_organization_change_minutes': None,
              'missing_observations': 0, 'causality_notice': 'Samoopis. Wynik nie dowodzi, że całą zmianę spowodowała aplikacja.'}
    if not trial:
        return result
    baseline = trial.get('baseline', {})
    base_days = (date.fromisoformat(baseline['end_date']) - date.fromisoformat(baseline['start_date'])).days + 1
    trial_days = (date.fromisoformat(trial['end_date']) - date.fromisoformat(trial['start_date'])).days + 1
    result['missing_observations'] = max(0, trial_days - len(outcomes))
    complete = result['missing_observations'] == 0 and all(o.get('worked_minutes') is not None for o in outcomes)
    result['baseline_status'] = 'complete' if baseline.get('worked_minutes') is not None else 'baseline_missing'
    result['observations_complete'] = complete
    if complete and base_days > 0:
        for field, actual, key in [('worked_minutes', 'actual_worked_minutes', 'normalized_work_change_minutes'), ('cost_grosz', 'actual_cost_grosz', 'normalized_cost_change_grosz'), ('organization_minutes', 'actual_organization_minutes', 'normalized_organization_change_minutes')]:
            if baseline.get(field) is not None and all(o.get(field) is not None for o in outcomes):
                result[key] = round(result[actual] - baseline[field] * trial_days / base_days, 2)
    return result


def serialize_plan(row):
    result = annotate(row.payload)
    result.update(id=row.id, version=row.version, updated_at=row.updated_at.isoformat())
    return result


def persist_update(db, row, expected, payload):
    if row.version != expected:
        raise HTTPException(409, 'Plan ma nowszą wersję. Wczytaj ją przed zapisem.')
    new_version = expected + 1
    updated_at = utcnow()
    changed = db.execute(update(Plan).where(Plan.id == row.id, Plan.owner == row.owner, Plan.version == expected)
                         .values(payload=payload, version=new_version, updated_at=updated_at))
    if changed.rowcount != 1:
        raise HTTPException(409, 'Plan zmieniono lub usunięto podczas operacji.')
    db.refresh(row)
    return serialize_plan(row)


def new_plan(owner, scenario, result, selected=None):
    selected = selected or (result.get('alternatives', [{}])[0].get('id') if result.get('alternatives') else None)
    payload = {'scenario': scenario, 'result': result, 'selected_alternative_id': selected, 'decisions': [], 'outcomes': [], 'trial': None,
               'versions': [{'version': scenario.get('version', 1), 'created_at': utcnow().isoformat(), 'scenario': scenario}], 'exports': []}
    return Plan(id=str(uuid.uuid4()), owner=owner, version=1, payload=payload, updated_at=utcnow())
