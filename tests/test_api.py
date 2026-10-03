from copy import deepcopy
import json
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, delete
from api.main import app
from api.database import Base, engine, SessionLocal, Plan, Tombstone, ExportSnapshot
from api.solver import solve_scenario


@pytest.fixture
def scenario():
    return json.loads(Path('data/synthetic/single-parent.json').read_text(encoding='utf-8'))


@pytest.fixture
def client(monkeypatch):
    async def inline(scenario):
        return solve_scenario(scenario, budget_seconds=10)
    monkeypatch.setattr('api.main.run_solver', inline)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        csrf = c.get('/api/session').json()['csrf_token']
        c.headers.update({'origin': 'http://testserver', 'X-CSRF-Token': csrf})
        yield c


def post(client, path, body, key=None):
    return client.post(path, json=body, headers={'Idempotency-Key': key or str(uuid.uuid4())})


def save(client, scenario):
    r = post(client, '/api/plans', {'scenario': scenario})
    assert r.status_code == 200, r.text
    return r.json()


def test_save_ownership_csrf_and_encryption(client, scenario):
    scenario['notes'] = 'SECRET-FAMILY-MARKER'
    plan = save(client, scenario)
    with TestClient(app) as stranger:
        stranger.get('/api/session')
        assert stranger.get('/api/plans/' + plan['id']).status_code == 404
    assert client.post('/api/plans', json={'scenario': scenario}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    with engine.connect() as db:
        raw = db.execute(text('SELECT payload FROM plans WHERE id=:id'), {'id': plan['id']}).scalar()
    assert b'SECRET-FAMILY-MARKER' not in raw
    assert client.get('/api/plans/' + plan['id']).headers['cache-control'] == 'no-store'


def test_idempotency_and_stale_version(client, scenario):
    key = str(uuid.uuid4())
    first = post(client, '/api/plans', {'scenario': scenario}, key)
    replay = post(client, '/api/plans', {'scenario': scenario}, key)
    assert first.json()['id'] == replay.json()['id']
    plan = first.json()
    changed = deepcopy(scenario)
    changed['notes'] = 'updated'
    assert post(client, '/api/plans', {'scenario': changed}, key).status_code == 409
    body = {'scenario': changed, 'expected_version': 1}
    assert post(client, f"/api/plans/{plan['id']}/versions", body).status_code == 200
    assert post(client, f"/api/plans/{plan['id']}/versions", body).status_code == 409


def test_export_preview_exact_allowlist_and_invalidated_edit(client, scenario):
    scenario['notes'] = 'DO-NOT-EXPORT-PRIVATE'
    scenario['care_resources'][0]['label'] = 'PRIVATE-FACILITY'
    result = client.post('/api/solve', json=scenario).json()
    assert result['alternatives'], result
    body = {'scenario': scenario, 'alternative_id': result['alternatives'][0]['id'], 'recipient': 'employer',
            'format': 'preview', 'input_version': 1, 'approved_fields': ['schedule', 'period', 'paid_minutes']}
    preview = client.post('/api/export', json=body)
    assert preview.status_code == 200, preview.text
    content = preview.json()
    assert 'PRIVATE-FACILITY' not in content['html']
    assert 'DO-NOT-EXPORT-PRIVATE' not in content['html']
    body.update(format='text', preview_id=content['preview_id'])
    exported = client.post('/api/export', json=body)
    assert exported.text == content['text']
    body['scenario']['notes'] = 'changed'
    assert client.post('/api/export', json=body).status_code == 409
    body.update(format='preview', approved_fields=['cost'])
    assert client.post('/api/export', json=body).status_code == 422


def accept_all(client, plan):
    alt = plan['result']['alternatives'][0]
    for dep in alt['dependencies']:
        r = post(client, f"/api/plans/{plan['id']}/decisions", {'expected_version': plan['version'],
            'alternative_id': alt['id'], 'dependency_id': dep['id'], 'decision': 'accepted',
            'party': 'Pracodawca', 'valid_until': plan['scenario']['end_date']})
        assert r.status_code == 200, r.text
        plan = r.json()
    return plan


def test_agreements_trial_observations_and_import_reset(client, scenario):
    plan = save(client, scenario)
    alt = plan['result']['alternatives'][0]
    baseline = {'start_date': '2026-09-28', 'end_date': '2026-10-04', 'worked_minutes': 1200, 'cost_grosz': 0, 'organization_minutes': 90}
    trial_body = {'expected_version': plan['version'], 'alternative_id': alt['id'], 'baseline': baseline}
    assert post(client, f"/api/plans/{plan['id']}/trial", trial_body).status_code == 409
    plan = accept_all(client, plan)
    assert plan['status'] == 'confirmed'
    trial_body['expected_version'] = plan['version']
    r = post(client, f"/api/plans/{plan['id']}/trial", trial_body)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan['status'] == 'trial' and not plan['trial']['blocked']
    assert plan['impact']['actual_worked_minutes'] == 0
    assert plan['impact']['normalized_work_change_minutes'] is None
    r = post(client, f"/api/plans/{plan['id']}/outcomes", {'expected_version': plan['version'], 'date': scenario['start_date'], 'worked_minutes': 480, 'cost_grosz': 1000, 'organization_minutes': 20})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan['impact']['actual_worked_minutes'] == 480
    backup = client.get(f"/api/plans/{plan['id']}/backup").json()
    restored = post(client, '/api/import', {'backup': backup}).json()
    assert restored['id'] != plan['id'] and restored['status'] != 'confirmed'
    assert restored['decisions'] == [] and restored['outcomes'] == []
    assert restored['restored_history']['outcomes'][0]['worked_minutes'] == 480
    changed = deepcopy(plan['scenario'])
    changed['care_resources'][0]['availability'][0]['excluded_dates'] = [scenario['start_date']]
    changed_plan = post(client, f"/api/plans/{plan['id']}/versions", {'scenario': changed, 'expected_version': plan['version']}).json()
    assert changed_plan['trial']['blocked']
    assert changed_plan['outcomes'][0]['worked_minutes'] == 480


def test_counterproposal_still_conflicts_and_refusal(client, scenario):
    plan = save(client, scenario)
    alt = plan['result']['alternatives'][0]
    dep = next(d for d in alt['dependencies'] if d['kind'] == 'employer')
    body = {'expected_version': plan['version'], 'alternative_id': alt['id'], 'dependency_id': dep['id'], 'party': 'Pracodawca', 'valid_until': scenario['end_date'], 'decision': 'rejected'}
    refused = post(client, f"/api/plans/{plan['id']}/decisions", body).json()
    assert refused['decisions'][-1]['decision'] == 'rejected'
    assert refused['rejected_alternatives']
    new_alt = refused['result']['alternatives'][0]
    assert new_alt['changes'] != alt['changes']
    body.update(expected_version=refused['version'], alternative_id=new_alt['id'], dependency_id=new_alt['dependencies'][0]['id'], decision='counterproposal', counterproposal_start='08:30')
    response = post(client, f"/api/plans/{plan['id']}/decisions", body)
    assert response.status_code == 200, response.text
    counter = response.json()
    assert counter['result']['status'] == 'INFEASIBLE'
    assert any(c.get('minutes') == 15 for c in counter['result']['conflicts'])


def test_delete_removes_history_and_replayed_save_cannot_resurrect(client, scenario):
    key = str(uuid.uuid4())
    plan = post(client, '/api/plans', {'scenario': scenario}, key).json()
    delete_key = str(uuid.uuid4())
    assert client.delete(f"/api/plans/{plan['id']}?expected_version={plan['version']}", headers={'Idempotency-Key': delete_key}).status_code == 200
    assert client.delete(f"/api/plans/{plan['id']}?expected_version={plan['version']}", headers={'Idempotency-Key': delete_key}).json() == {'deleted': True}
    assert client.get('/api/plans/' + plan['id']).status_code == 404
    assert post(client, '/api/plans', {'scenario': scenario}, key).status_code == 410
    assert post(client, f"/api/plans/{plan['id']}/versions", {'scenario': scenario, 'expected_version': 1}).status_code == 404


def test_bad_import_and_sensitive_validation(client, scenario):
    assert post(client, '/api/import', {'backup': {'backup_schema_version': 2}}).status_code == 422
    bad = deepcopy(scenario)
    bad['unexpected'] = 'PRIVATE-VALIDATION-MARKER'
    response = client.post('/api/solve', json=bad)
    assert response.status_code == 422 and 'PRIVATE-VALIDATION-MARKER' not in response.text


def test_trial_repair_keeps_observation_history(client, scenario):
    plan = accept_all(client, save(client, scenario))
    baseline = {'start_date': '2026-09-28', 'end_date': '2026-10-04', 'worked_minutes': 1200}
    plan = post(client, f"/api/plans/{plan['id']}/trial", {'expected_version': plan['version'],
        'alternative_id': plan['selected_alternative_id'], 'baseline': baseline}).json()
    plan = post(client, f"/api/plans/{plan['id']}/outcomes", {'expected_version': plan['version'],
        'date': scenario['start_date'], 'worked_minutes': 420}).json()
    changed = deepcopy(plan['scenario'])
    changed['notes'] = 'Nowa informacja do ponownego sprawdzenia'
    plan = post(client, f"/api/plans/{plan['id']}/versions", {'expected_version': plan['version'], 'scenario': changed}).json()
    assert plan['trial']['blocked']
    response = post(client, f"/api/plans/{plan['id']}/trial/repair", {'expected_version': plan['version'],
        'alternative_id': plan['selected_alternative_id']})
    assert response.status_code == 200, response.text
    repaired = response.json()
    assert not repaired['trial']['blocked']
    assert repaired['outcomes'][0]['worked_minutes'] == 420
    assert len(repaired['trial']['repairs']) == 1
    assert repaired['impact']['synthetic'] is True


def test_baseline_must_precede_trial_and_fit_duration(client, scenario):
    plan = accept_all(client, save(client, scenario))
    body = {'expected_version': plan['version'], 'alternative_id': plan['selected_alternative_id'],
            'baseline': {'start_date': scenario['start_date'], 'end_date': scenario['end_date'], 'worked_minutes': 60}}
    assert post(client, f"/api/plans/{plan['id']}/trial", body).status_code == 422
    body['baseline'] = {'start_date': '2026-10-02', 'end_date': '2026-10-02', 'worked_minutes': 1500}
    assert post(client, f"/api/plans/{plan['id']}/trial", body).status_code == 422


def test_personal_plan_cannot_record_future_actual_work(client, scenario, monkeypatch):
    from datetime import date
    monkeypatch.setattr('api.main.warsaw_today', lambda: date(2026, 10, 3))
    scenario['data_mode'] = 'personal'
    plan = accept_all(client, save(client, scenario))
    response = post(client, f"/api/plans/{plan['id']}/trial", {'expected_version': plan['version'],
        'alternative_id': plan['selected_alternative_id'], 'baseline': {'start_date': '2026-09-28', 'end_date': '2026-10-02', 'worked_minutes': 1200}})
    assert response.status_code == 200, response.text
    plan = response.json()
    response = post(client, f"/api/plans/{plan['id']}/outcomes", {'expected_version': plan['version'],
        'date': '2026-10-05', 'worked_minutes': 480})
    assert response.status_code == 422


def test_observation_date_uses_warsaw_at_utc_day_boundary(client, scenario, monkeypatch):
    from datetime import datetime, timezone
    from api.calendar_clock import warsaw_today
    # 22:30 UTC is already 00:30 on the next civil day in Warsaw.
    local_day = warsaw_today(datetime(2026, 10, 4, 22, 30, tzinfo=timezone.utc))
    assert local_day.isoformat() == '2026-10-05'
    monkeypatch.setattr('api.main.warsaw_today', lambda: local_day)
    monkeypatch.setattr('api.plans.warsaw_today', lambda: local_day)
    scenario['data_mode'] = 'personal'
    plan = accept_all(client, save(client, scenario))
    response = post(client, f"/api/plans/{plan['id']}/trial", {'expected_version': plan['version'],
        'alternative_id': plan['selected_alternative_id'], 'baseline': {'start_date': '2026-09-28', 'end_date': '2026-10-02', 'worked_minutes': 1200}})
    assert response.status_code == 200, response.text
    plan = response.json()
    response = post(client, f"/api/plans/{plan['id']}/outcomes", {'expected_version': plan['version'],
        'date': '2026-10-05', 'worked_minutes': 0})
    assert response.status_code == 200, response.text
    plan = response.json()
    response = post(client, f"/api/plans/{plan['id']}/outcomes", {'expected_version': plan['version'],
        'date': '2026-10-06', 'worked_minutes': 0})
    assert response.status_code == 422


def test_care_refusal_recomputes_instead_of_recommending_same_place(client, scenario):
    scenario['care_resources'][0]['confirmed'] = False
    scenario['activities'][0]['start'] = '08:00'
    scenario['activities'][0]['negotiable'] = False
    plan = save(client, scenario)
    alternative = plan['result']['alternatives'][0]
    dependency = next(d for d in alternative['dependencies'] if d['kind'] == 'care')
    response = post(client, f"/api/plans/{plan['id']}/decisions", {'expected_version': plan['version'],
        'alternative_id': alternative['id'], 'dependency_id': dependency['id'], 'decision': 'rejected',
        'party': 'Placówka', 'valid_until': scenario['end_date']})
    assert response.status_code == 200, response.text
    refused = response.json()
    assert refused['result']['status'] == 'INFEASIBLE'
    assert refused['result']['alternatives'] == []
    assert refused['rejected_alternatives']


def test_public_catalog_is_separate_from_synthetic(client):
    response = client.get('/api/catalog?mode=verified')
    assert response.status_code == 200
    assert response.json()['records']
    assert all(not r['synthetic'] for r in response.json()['records'])
    assert client.get('/api/catalog?mode=invalid').status_code == 422


def test_handoff_refusal_recomputes_with_scoped_exclusion(client):
    scenario = json.loads(Path('data/synthetic/care-handoff.json').read_text(encoding='utf-8'))
    scenario['care_needs'][0]['arrangements'][0]['handoffs'][0]['confirmed'] = False
    plan = save(client, scenario)
    alternative = plan['result']['alternatives'][0]
    dependency = next(d for d in alternative['dependencies'] if d['kind'] == 'care_handoff')
    response = post(client, f"/api/plans/{plan['id']}/decisions", {'expected_version': plan['version'],
        'alternative_id': alternative['id'], 'dependency_id': dependency['id'], 'decision': 'rejected',
        'party': 'Opiekun', 'valid_until': scenario['end_date']})
    assert response.status_code == 200, response.text
    assert response.json()['result']['status'] == 'INFEASIBLE'
    assert response.json()['scenario']['care_needs'][0]['arrangements'][0]['unavailable']


def test_import_resets_handoff_acceptance_and_source(client):
    scenario = json.loads(Path('data/synthetic/care-handoff.json').read_text(encoding='utf-8'))
    scenario['care_needs'][0]['arrangements'][0]['handoffs'][0]['confirmed'] = True
    plan = save(client, scenario)
    backup = client.get(f"/api/plans/{plan['id']}/backup").json()
    restored = post(client, '/api/import', {'backup': backup}).json()
    handoff = restored['scenario']['care_needs'][0]['arrangements'][0]['handoffs'][0]
    assert handoff['confirmed'] is False and handoff['valid_to'] is None
    assert handoff['source']['status'] == 'unknown'
    assert restored['status'] != 'confirmed'


def test_delete_during_solve_cannot_write_late_version(client, scenario, monkeypatch):
    plan = save(client, scenario)
    async def solve_then_delete(value):
        with SessionLocal() as db:
            db.execute(delete(Plan).where(Plan.id == plan['id']))
            db.add(Tombstone(id=plan['id']))
            db.commit()
        return solve_scenario(value)
    monkeypatch.setattr('api.main.run_solver', solve_then_delete)
    response = post(client, f"/api/plans/{plan['id']}/versions", {'expected_version': plan['version'], 'scenario': scenario})
    assert response.status_code == 409, response.text
    assert client.get('/api/plans/' + plan['id']).status_code == 404


def test_disconnected_save_does_not_persist_after_calculation(client, scenario, monkeypatch):
    before = len(client.get('/api/session').json()['saved_plans'])
    async def disconnected(self):
        return True
    monkeypatch.setattr('starlette.requests.Request.is_disconnected', disconnected)
    response = post(client, '/api/plans', {'scenario': scenario})
    assert response.status_code == 499
    assert len(client.get('/api/session').json()['saved_plans']) == before


def test_delete_cascades_export_snapshot_and_racing_export_fails(client, scenario, monkeypatch):
    plan = save(client, scenario)
    body = {'plan_id': plan['id'], 'scenario': plan['scenario'], 'input_version': plan['version'],
            'alternative_id': plan['selected_alternative_id'], 'recipient': 'employer', 'format': 'preview'}
    preview = client.post('/api/export', json=body).json()
    body.update(format='text', preview_id=preview['preview_id'])
    assert client.post('/api/export', json=body).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(ExportSnapshot).where(ExportSnapshot.plan_id == plan['id'])) is not None
    async def solve_then_delete(value):
        with SessionLocal() as db:
            db.execute(delete(Plan).where(Plan.id == plan['id']))
            db.add(Tombstone(id=plan['id']))
            db.commit()
        return solve_scenario(value)
    monkeypatch.setattr('api.main.run_solver', solve_then_delete)
    response = client.post('/api/export', json=body)
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.scalar(select(ExportSnapshot).where(ExportSnapshot.plan_id == plan['id'])) is None
