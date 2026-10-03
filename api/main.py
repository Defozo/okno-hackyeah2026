import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text, delete
from sqlalchemy.exc import IntegrityError

from api.contracts import SaveRequest, VersionRequest, DecisionRequest, TrialRequest, RepairTrialRequest, OutcomeRequest, ExportRequest, ImportRequest
from api.database import Base, SessionLocal, engine, Plan, Operation, Tombstone, ExportSnapshot, utcnow
from api.domain import Scenario
from api.exports import card_data, digest, preview_token, verify_preview, render_html, render_text, render_pdf, render_ics
from api.plans import find_plan, new_plan, serialize_plan, operation_identity, prior_operation, record_operation, persist_update, alternative_for, dependency_fingerprint, annotate, reset_source_claims
from api.security import require_owner, issue_session, owner_id, csrf_for, rate_limit
from api.settings import settings
from api.worker import run_solver
from api.calendar_clock import warsaw_today

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app):
    if len(settings.session_secret) < 32 or not settings.encryption_key:
        raise RuntimeError('Inject OKNO_SESSION_SECRET and OKNO_ENCRYPTION_KEY through psst.')
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    yield


app = FastAPI(title='Okno API', version='1.0.0', lifespan=lifespan)


@app.exception_handler(IntegrityError)
async def duplicate_operation(request: Request, exc):
    # A simultaneous retry can race at COMMIT. The unique operation key is the arbiter.
    try:
        owner = require_owner(request)
        body = {'expected_version': int(request.query_params['expected_version'])} if request.method == 'DELETE' else await request.json()
        identity, request_hash = operation_identity(request, owner, body)
        with SessionLocal() as db:
            prior = prior_operation(db, identity, request_hash)
            if prior is not None:
                return JSONResponse(prior)
    except Exception:
        pass
    return JSONResponse({'detail': 'Konflikt równoczesnego zapisu. Wczytaj aktualny plan.'}, status_code=409)


@app.middleware('http')
async def protections(request, call_next):
    if request.url.path.startswith('/api/'):
        try:
            rate_limit(request)
        except HTTPException as error:
            return JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)
        try:
            content_length = int(request.headers.get('content-length', '0') or '0')
        except ValueError:
            return JSONResponse({'detail': 'Niepoprawna długość żądania.'}, status_code=400)
        if content_length > 2_000_000:
            return JSONResponse({'detail': 'Plik przekracza 2 MB.'}, status_code=413)
        # Enforce limits also for chunked bodies. Content is never logged.
        if request.method in ('POST', 'PUT', 'PATCH'):
            received = bytearray()
            async for chunk in request.stream():
                received.extend(chunk)
                if len(received) > 2_000_000:
                    return JSONResponse({'detail': 'Plik przekracza 2 MB.'}, status_code=413)
            request._body = bytes(received)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic input values may contain private notes; return only paths and messages.
    return JSONResponse(status_code=422, content={'detail': [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]})


def database():
    with SessionLocal() as db:
        yield db


async def solve_for_request(request, scenario):
    result = await run_solver(scenario)
    if await request.is_disconnected():
        raise HTTPException(499, 'Połączenie anulowano. Wynik nie został zapisany.')
    return result


@app.get('/health/live')
def live():
    return {'status': 'ok'}


@app.get('/health/ready')
async def ready():
    try:
        with engine.connect() as db:
            db.execute(text('SELECT id FROM plans LIMIT 1'))
        components = {'database': 'ready', 'solver': 'ready', 'routing': settings.routing_mode}
        if settings.routing_mode == 'otp':
            from api.routes import otp_readiness
            components['otp'] = otp_readiness()
            import httpx
            import os
            async with httpx.AsyncClient(timeout=3) as client:
                probe = await client.post(os.getenv('OTP_URL', 'http://otp:8080') + '/otp/gtfs/v1', json={'query': '{ __typename }'})
            if probe.status_code != 200 or not components['otp'].get('graph_verified'):
                return JSONResponse({'status': 'degraded', 'components': components}, status_code=503)
        return {'status': 'ready', 'components': components}
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)


@app.get('/api/session')
def session(request: Request, response: Response, db=Depends(database)):
    token = issue_session(request, response)
    rows = db.scalars(select(Plan).where(Plan.owner == owner_id(token))).all()
    return {'csrf_token': csrf_for(token), 'saved_plans': [{'id': p.id, 'title': p.payload['scenario']['title'], 'version': p.version, 'updated_at': p.updated_at.isoformat()} for p in rows],
            'data_mode': settings.data_mode, 'routing_mode': settings.routing_mode, 'retention_days': settings.retention_days}


@app.get('/api/examples')
def examples():
    items = []
    for path in sorted((ROOT / 'data/synthetic').glob('*.json')):
        if path.stem.startswith('benchmark'):
            continue
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        scenario = raw.get('scenario', raw)
        if 'activities' in scenario:
            items.append({'id': path.stem, 'title': scenario.get('title', path.stem), 'description': raw.get('description', 'Przykład syntetyczny. Nie przedstawia rzeczywistego wyniku.'), 'scenario': scenario})
    return {'items': items}


@app.get('/api/catalog')
def catalog(mode: str | None = None):
    from api.catalog import load_catalog
    if mode is not None and mode not in ('synthetic', 'verified', 'all'):
        raise HTTPException(422, 'Nieznany tryb katalogu.')
    return load_catalog(mode or settings.data_mode)


@app.post('/api/solve')
async def solve(scenario: Scenario, request: Request, owner=Depends(require_owner)):
    return await solve_for_request(request, scenario.model_dump(mode='json'))


from api.routes import RoutesRequest


@app.post('/api/routes')
async def routes(body: RoutesRequest, owner=Depends(require_owner)):
    from api.routes import get_routes
    return await get_routes(body.model_dump(mode='json'))


@app.post('/api/plans')
async def create_plan(body: SaveRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    result = await solve_for_request(request, body.scenario.model_dump(mode='json'))
    row = new_plan(owner, body.scenario.model_dump(mode='json'), result, body.selected_alternative_id)
    db.add(row)
    response = serialize_plan(row)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.get('/api/plans/{plan_id}')
def get_plan(plan_id: str, owner=Depends(require_owner), db=Depends(database)):
    return serialize_plan(find_plan(db, plan_id, owner))


@app.post('/api/plans/{plan_id}/versions')
async def version_plan(plan_id: str, body: VersionRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    if row.version != body.expected_version:
        raise HTTPException(409, 'Plan ma nowszą wersję.')
    scenario = body.scenario.model_dump(mode='json')
    scenario['version'] = row.payload['scenario']['version'] + 1
    result = await solve_for_request(request, scenario)
    payload = deepcopy(row.payload)
    payload.update(scenario=scenario, result=result)
    payload['selected_alternative_id'] = body.selected_alternative_id or (result['alternatives'][0]['id'] if result.get('alternatives') else None)
    payload['versions'].append({'version': scenario['version'], 'created_at': utcnow().isoformat(), 'scenario': scenario})
    response = persist_update(db, row, body.expected_version, payload)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.post('/api/plans/{plan_id}/decisions')
async def decision_plan(plan_id: str, body: DecisionRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    if row.version != body.expected_version:
        raise HTTPException(409, 'Plan ma nowszą wersję.')
    payload = deepcopy(row.payload)
    alternative = alternative_for(payload, body.alternative_id)
    if not alternative:
        raise HTTPException(422, 'Wybierz aktualny wariant planu.')
    dependency = next((d for d in alternative.get('dependencies', []) if d['id'] == body.dependency_id), None)
    if not dependency:
        raise HTTPException(422, 'Zależność nie należy do wybranego wariantu.')
    decision = body.model_dump(mode='json')
    decision.update(id=str(uuid.uuid4()), recorded_at=utcnow().isoformat(), input_version=payload['scenario']['version'],
                    fingerprint=dependency_fingerprint(payload['scenario'], alternative, dependency))
    payload['decisions'].append(decision)
    payload['selected_alternative_id'] = alternative['id']
    if body.decision == 'rejected' and dependency.get('kind') == 'employer':
        scenario = deepcopy(payload['scenario'])
        target = dependency.get('activity_id')
        proposal = dependency.get('proposal', {})
        proposed_start = proposal.get('start')
        refused_activities = proposal.get('activities') or [{'activity_id': target, 'start': proposed_start}]
        if target and proposed_start:
            for refused in refused_activities:
                scenario.setdefault('forbidden_proposals', []).append({'activity_id': refused.get('activity_id', refused.get('id')), 'start': refused['start'],
                    'valid_from': scenario['start_date'], 'valid_to': str(body.valid_until), 'reason': 'Zapisana odmowa zmiany godzin'})
            scenario['version'] += 1
            payload.setdefault('rejected_alternatives', []).append({'alternative': alternative, 'decision_id': decision['id'], 'scenario_version': payload['scenario']['version']})
            payload['scenario'] = Scenario.model_validate(scenario).model_dump(mode='json')
            payload['result'] = await solve_for_request(request, payload['scenario'])
            payload['selected_alternative_id'] = payload['result']['alternatives'][0]['id'] if payload['result'].get('alternatives') else None
            payload['versions'].append({'version': scenario['version'], 'created_at': utcnow().isoformat(), 'scenario': payload['scenario'], 'reason': 'rejection'})
    if body.decision == 'rejected' and dependency.get('kind') in ('care', 'care_handoff'):
        scenario = deepcopy(payload['scenario'])
        refused_period = {'weekdays': list(range(7)), 'valid_from': scenario['start_date'], 'valid_to': str(body.valid_until)}
        if dependency['kind'] == 'care':
            resource = next(r for r in scenario['care_resources'] if r['id'] == dependency['resource_id'])
            resource.setdefault('busy', []).append({'start': '00:00', 'end': '24:00', **refused_period})
        else:
            need = next(n for n in scenario['care_needs'] if n['id'] == dependency['need_id'])
            arrangement = next(a for a in need['arrangements'] if a['id'] == dependency['arrangement_id'])
            arrangement.setdefault('unavailable', []).append(refused_period)
        scenario['version'] += 1
        payload.setdefault('rejected_alternatives', []).append({'alternative': alternative, 'decision_id': decision['id'], 'scenario_version': payload['scenario']['version']})
        payload['scenario'] = Scenario.model_validate(scenario).model_dump(mode='json')
        payload['result'] = await solve_for_request(request, payload['scenario'])
        payload['selected_alternative_id'] = payload['result']['alternatives'][0]['id'] if payload['result'].get('alternatives') else None
        payload['versions'].append({'version': scenario['version'], 'created_at': utcnow().isoformat(), 'scenario': payload['scenario'], 'reason': 'care_rejection'})
    if body.decision == 'counterproposal':
        if dependency.get('kind') != 'employer':
            raise HTTPException(422, 'Kontrpropozycja godzin dotyczy zależności grafiku pracy.')
        if not body.counterproposal_start:
            raise HTTPException(422, 'Podaj proponowaną godzinę rozpoczęcia.')
        scenario = deepcopy(payload['scenario'])
        aid = dependency.get('activity_id')
        ids = {f.split('.')[1] for f in dependency.get('fields', []) if f.startswith('activities.') and len(f.split('.')) >= 2}
        if aid:
            ids.add(aid)
        candidates = [a for a in scenario['activities'] if a['id'] in ids] if ids else [a for a in scenario['activities'] if a['kind'] == 'work']
        if not candidates:
            raise HTTPException(422, 'Ta zależność nie jest zmianą godzin pracy.')
        try:
            def minutes(value):
                h, m = map(int, value.split(':'))
                if not 0 <= h < 24 or not 0 <= m < 60:
                    raise ValueError()
                return 60 * h + m
            first = next((a for a in candidates if a['id'] == aid), candidates[0])
            shift = minutes(body.counterproposal_start) - minutes(first['start'])
            for activity in candidates:
                hour = minutes(activity['start']) + shift
                if not 0 <= hour < 1440:
                    raise ValueError()
                start = f'{hour // 60:02d}:{hour % 60:02d}'
                activity['start'] = start
                activity['start_min'] = start
                activity['start_max'] = start
        except (ValueError, TypeError):
            raise HTTPException(422, 'Niepoprawna godzina kontrpropozycji dla objętego grafiku.')
        # A new concrete counterproposal is considered even if a prior refusal covered it.
        scenario['forbidden_proposals'] = [r for r in scenario.get('forbidden_proposals', []) if not (r['activity_id'] in {a['id'] for a in candidates} and r['start'] == body.counterproposal_start)]
        scenario['version'] += 1
        scenario = Scenario.model_validate(scenario).model_dump(mode='json')
        payload['scenario'] = scenario
        payload['result'] = await solve_for_request(request, scenario)
        payload['selected_alternative_id'] = payload['result']['alternatives'][0]['id'] if payload['result'].get('alternatives') else None
        payload['versions'].append({'version': scenario['version'], 'created_at': utcnow().isoformat(), 'scenario': scenario, 'reason': 'counterproposal'})
    response = persist_update(db, row, body.expected_version, payload)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.post('/api/plans/{plan_id}/trial')
async def start_trial(plan_id: str, body: TrialRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    payload = deepcopy(row.payload)
    if payload.get('trial'):
        raise HTTPException(409, 'Próba jest już zapisana. Jej historia pozostaje zachowana.')
    payload['selected_alternative_id'] = body.alternative_id
    payload['result'] = await solve_for_request(request, payload['scenario'])
    alt = alternative_for(annotate(payload))
    if not alt or alt['status'] != 'confirmed':
        raise HTTPException(409, 'Próba wymaga aktualnych obliczeń i potwierdzenia wszystkich zależności.')
    baseline = body.baseline.model_dump(mode='json')
    if body.baseline.end_date < body.baseline.start_date:
        raise HTTPException(422, 'Niepoprawny okres odniesienia.')
    if payload['scenario'].get('data_mode') != 'synthetic' and body.baseline.end_date > warsaw_today():
        raise HTTPException(422, 'Rzeczywisty okres odniesienia nie może obejmować przyszłości.')
    start = str(body.start_date or payload['scenario']['start_date'])
    end = str(body.end_date or payload['scenario']['end_date'])
    if not payload['scenario']['start_date'] <= start <= end <= payload['scenario']['end_date']:
        raise HTTPException(422, 'Próba musi mieścić się w sprawdzonym okresie.')
    if baseline['end_date'] >= start:
        raise HTTPException(422, 'Okres odniesienia musi zakończyć się przed początkiem próby.')
    baseline_days = (body.baseline.end_date - body.baseline.start_date).days + 1
    if any((baseline.get(field) or 0) > baseline_days * 1440 for field in ('worked_minutes', 'organization_minutes')):
        raise HTTPException(422, 'Zapisany czas przekracza długość okresu odniesienia.')
    payload['trial'] = {'id': str(uuid.uuid4()), 'start_date': start, 'end_date': end, 'baseline': baseline,
                        'scenario_hash': digest(payload['scenario']), 'alternative_snapshot': alt,
                        'started_at': utcnow().isoformat(), 'completed': False}
    response = persist_update(db, row, body.expected_version, payload)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.post('/api/plans/{plan_id}/outcomes')
def add_outcome(plan_id: str, body: OutcomeRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    payload = deepcopy(row.payload)
    trial = payload.get('trial')
    if not trial or not trial['start_date'] <= str(body.date) <= trial['end_date']:
        raise HTTPException(422, 'Obserwacja musi dotyczyć daty zapisanej próby.')
    if payload['scenario'].get('data_mode') != 'synthetic' and body.date > warsaw_today():
        raise HTTPException(422, 'Rzeczywista obserwacja nie może dotyczyć przyszłej daty.')
    item = body.model_dump(mode='json')
    item.update(id=str(uuid.uuid4()), recorded_at=utcnow().isoformat())
    # One daily observation, with previous revisions retained for provenance.
    previous = [o for o in payload['outcomes'] if o['date'] == str(body.date)]
    if previous:
        payload.setdefault('outcome_history', []).extend(previous)
    payload['outcomes'] = [o for o in payload['outcomes'] if o['date'] != str(body.date)] + [item]
    if body.complete_trial:
        trial['completed'] = True
    response = persist_update(db, row, body.expected_version, payload)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.post('/api/plans/{plan_id}/trial/repair')
async def repair_trial(plan_id: str, body: RepairTrialRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    payload = deepcopy(row.payload)
    if not payload.get('trial') or payload['trial'].get('completed'):
        raise HTTPException(409, 'Naprawa dotyczy rozpoczętej, niezakończonej próby.')
    payload['result'] = await solve_for_request(request, payload['scenario'])
    payload['selected_alternative_id'] = body.alternative_id
    alt = alternative_for(annotate(payload))
    if not alt or alt['status'] != 'confirmed':
        raise HTTPException(409, 'Naprawa wymaga aktualnych obliczeń i wszystkich potrzebnych ustaleń.')
    trial = payload['trial']
    if not payload['scenario']['start_date'] <= trial['start_date'] <= trial['end_date'] <= payload['scenario']['end_date']:
        raise HTTPException(409, 'Aktualne obliczenia muszą obejmować pełen zapisany okres próby.')
    trial.setdefault('repairs', []).append({'recorded_at': utcnow().isoformat(), 'previous_scenario_hash': trial['scenario_hash'],
                                          'previous_alternative': trial['alternative_snapshot']})
    trial['scenario_hash'] = digest(payload['scenario'])
    trial['alternative_snapshot'] = alt
    response = persist_update(db, row, body.expected_version, payload)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.post('/api/export')
async def export(body: ExportRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    if body.format == 'ics' and not body.plan_id:
        raise HTTPException(422, 'Zapisz plan przed eksportem kalendarza, aby zachować osobne i stabilne identyfikatory zdarzeń.')
    status = 'proposal'
    if body.plan_id:
        row = find_plan(db, body.plan_id, owner)
        if row.payload['scenario'] != body.scenario.model_dump(mode='json') or str(row.version) != str(body.input_version):
            raise HTTPException(409, 'Podgląd nie jest zgodny z aktualną wersją planu.')
        result = await solve_for_request(request, row.payload['scenario'])
        payload = deepcopy(row.payload)
        payload['result'] = result
        alt = alternative_for(annotate(payload), body.alternative_id)
        status = 'confirmed' if alt and alt.get('status') == 'confirmed' else 'proposal'
    else:
        result = await solve_for_request(request, body.scenario.model_dump(mode='json'))
        alt = next((a for a in result.get('alternatives', []) if a['id'] == body.alternative_id), None)
    if body.alternative_id and not alt:
        raise HTTPException(409, 'Wybrany wariant nie jest aktualny. Przelicz plan.')
    card = card_data(body, result, alt, status, trial=payload.get('trial') if body.plan_id else None)
    if body.format == 'preview':
        token, expires = preview_token(owner, body, card)
        return {'preview_id': token, 'expires_at': expires, 'html': render_html(card), 'text': render_text(card), 'fields': card['fields'], 'card': card}
    verify_preview(owner, body, card)
    if body.plan_id:
        # Re-read after the solver await, then serialize export creation with deletion.
        current = db.scalar(select(Plan).where(Plan.id == body.plan_id, Plan.owner == owner)
                            .with_for_update().execution_options(populate_existing=True))
        if not current or current.version != int(body.input_version):
            raise HTTPException(409, 'Plan zmieniono lub usunięto podczas przygotowania eksportu.')
        snapshot_id = digest({'plan': body.plan_id, 'version': body.input_version, 'card': card})
        if not db.get(ExportSnapshot, snapshot_id):
            db.add(ExportSnapshot(id=snapshot_id, owner=owner, plan_id=body.plan_id, payload=card))
            db.commit()
    headers = {'Content-Disposition': f'attachment; filename="okno-karta.{"txt" if body.format == "text" else body.format}"'}
    if body.format == 'html':
        return Response(render_html(card), media_type='text/html', headers=headers)
    if body.format == 'text':
        return Response(render_text(card), media_type='text/plain', headers=headers)
    if body.format == 'ics':
        return Response(render_ics(card, body.plan_id or owner), media_type='text/calendar', headers=headers)
    return Response(await render_pdf(card), media_type='application/pdf', headers=headers)


@app.get('/api/plans/{plan_id}/backup')
def backup(plan_id: str, owner=Depends(require_owner), db=Depends(database)):
    row = find_plan(db, plan_id, owner)
    return {'backup_schema_version': 1, 'exported_at': utcnow().isoformat(), 'warning': 'Prywatna kopia własna. Nie przekazuj jej odbiorcy karty.', 'plan': serialize_plan(row)}


@app.post('/api/import')
async def import_backup(body: ImportRequest, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, body.model_dump(mode='json'))
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    backup = body.backup
    if backup.get('backup_schema_version') != 1 or not isinstance(backup.get('plan'), dict):
        raise HTTPException(422, 'Nieobsługiwany schemat kopii.')
    try:
        scenario = Scenario.model_validate(backup['plan']['scenario']).model_dump(mode='json')
    except Exception:
        raise HTTPException(422, 'Kopia zawiera niepoprawny scenariusz.')
    # Historical source claims are not new confirmations. The editor exposes each
    # status so the owner can check the data again before a restored plan is used.
    reset_source_claims(scenario)
    result = await solve_for_request(request, scenario)
    row = new_plan(owner, scenario, result)
    # Imported claims are history, never authorization to begin a new trial.
    row.payload['restored_history'] = {k: backup['plan'].get(k) for k in ('decisions', 'outcomes', 'trial', 'versions')}
    row.payload['import_notice'] = 'Kopia odtworzona jako nowy plan. Dawne ustalenia wymagają ponownego potwierdzenia.'
    db.add(row)
    response = serialize_plan(row)
    record_operation(db, identity, request_hash, owner, response, row.id)
    db.commit()
    return response


@app.delete('/api/plans/{plan_id}')
def delete_plan(plan_id: str, expected_version: int, request: Request, owner=Depends(require_owner), db=Depends(database)):
    identity, request_hash = operation_identity(request, owner, {'expected_version': expected_version})
    prior = prior_operation(db, identity, request_hash)
    if prior is not None:
        return prior
    row = find_plan(db, plan_id, owner)
    if row.version != expected_version:
        raise HTTPException(409, 'Plan ma nowszą wersję.')
    deleted = db.execute(delete(Plan).where(Plan.id == plan_id, Plan.version == expected_version, Plan.owner == owner))
    if deleted.rowcount != 1:
        raise HTTPException(409, 'Plan zmienił się podczas usuwania.')
    db.add(Tombstone(id=plan_id))
    db.execute(delete(ExportSnapshot).where(ExportSnapshot.plan_id == plan_id))
    # Keep minimal operation tombstones, erase private response copies.
    for op in db.scalars(select(Operation).where(Operation.plan_id == plan_id)):
        op.response = {'deleted': True}
    record_operation(db, identity, request_hash, owner, {'deleted': True})
    db.commit()
    return {'deleted': True}


if (ROOT / 'web/dist').exists():
    app.mount('/assets', StaticFiles(directory=ROOT / 'web/dist/assets'), name='assets')


@app.get('/{path:path}', include_in_schema=False)
def spa(path: str):
    if path.startswith(('api/', 'health/')):
        raise HTTPException(404)
    root = (ROOT / 'web/dist').resolve()
    target = (root / path).resolve()
    if target.is_relative_to(root) and target.is_file():
        return FileResponse(target)
    if (root / 'index.html').exists():
        return FileResponse(root / 'index.html')
    return JSONResponse({'detail': 'Frontend nie został zbudowany. Uruchom npm run build w web/.'}, status_code=503)
