"""Exercise the deployed API, real OTP, PostgreSQL and optional local TLS."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
import socket
import ssl
from urllib.parse import urlsplit
import httpx

ROOT = Path(__file__).resolve().parents[1]
base = os.getenv('OKNO_API_URL', 'http://host.docker.internal:18430')
origin = os.getenv('OKNO_ORIGIN', 'http://localhost:18430')
tls = base.startswith('https:')
if os.getenv('OKNO_HOST_ALIAS'):
    original_lookup = socket.getaddrinfo
    def lookup(host, *args, **kwargs):
        return original_lookup(os.environ['OKNO_HOST_ALIAS'] if host in ('localhost', b'localhost') else host, *args, **kwargs)
    socket.getaddrinfo = lookup
verification = ssl.create_default_context(cafile=os.environ['OKNO_CA_PATH']) if os.getenv('OKNO_CA_PATH') else not bool(os.getenv('OKNO_TEST_LOCAL_CA'))
report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'origin': origin,
          'synthetic_care_and_prices': True, 'local_tls': tls, 'public_https_verified': False, 'checks': []}
if tls and os.getenv('OKNO_CA_PATH'):
    endpoint = urlsplit(base)
    trust = ssl.create_default_context(cafile=os.environ['OKNO_CA_PATH'])
    with socket.create_connection((endpoint.hostname, endpoint.port or 443), timeout=10) as connection:
        with trust.wrap_socket(connection, server_hostname='localhost') as secured:
            report['tls_certificate'] = {'local_ca_chain_verified': True, 'hostname_verified': 'localhost', 'protocol': secured.version()}
with httpx.Client(base_url=base, timeout=45, verify=verification) as client:
    health = client.get('/health/ready')
    health.raise_for_status()
    report['readiness'] = health.json()
    session = client.get('/api/session')
    session.raise_for_status()
    cookie = session.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert ('; secure' in cookie) == tls
    client.headers.update({'origin': origin, 'x-csrf-token': session.json()['csrf_token']})
    report['checks'].append('Session cookie flags and exact origin')
    scenario = json.loads((ROOT / 'data/synthetic/two-dependents.json').read_text(encoding='utf-8'))
    scenario.update(start_date='2026-10-05', end_date='2026-10-05', minimum_paid_minutes=480, self_care_capacity=2)
    scenario['activities'][0]['step_minutes'] = 30
    scenario['location_coordinates'] = {
        'home': {'lat': 50.06455, 'lon': 19.96144}, 'care': {'lat': 50.06577, 'lon': 19.95957},
        'care-2': {'lat': 50.06594, 'lon': 19.94587}, 'work': {'lat': 50.06435, 'lon': 19.93868}}
    for leg in scenario['travel_legs']:
        leg['mode'] = 'transit'
        leg['bands'] = [{'start': '00:00', 'end': '24:00', 'minutes': 1, 'cost_grosze': 0}]
    started = time.monotonic()
    response = client.post('/api/solve', json=scenario)
    response.raise_for_status()
    result = response.json()
    assert result['status'] in ('OPTIMAL', 'FEASIBLE'), result
    assert result['routing']['complete'] and result['routing']['queries'] >= 18
    assert result['alternatives'] and all(a['validation']['valid'] for a in result['alternatives'])
    report['solve'] = {'status': result['status'], 'queries': result['routing']['queries'],
                       'alternatives': len(result['alternatives']), 'elapsed_seconds': round(time.monotonic() - started, 3)}
    report['checks'].append('Real OTP candidate routes, isolated solver and independent validator through HTTP')
    key = str(uuid.uuid4())
    saved = client.post('/api/plans', json={'scenario': scenario}, headers={'idempotency-key': key})
    saved.raise_for_status()
    plan = saved.json()
    assert client.post('/api/plans', json={'scenario': scenario}, headers={'idempotency-key': key}).json()['id'] == plan['id']
    assert client.get('/api/plans/' + plan['id']).json()['version'] == plan['version']
    report['checks'].append('PostgreSQL save, read and idempotent retry')
    with httpx.Client(base_url=base, verify=verification) as stranger:
        stranger.get('/api/session')
        assert stranger.get('/api/plans/' + plan['id']).status_code == 404
    report['checks'].append('Another session cannot read the saved plan')
    body = {'scenario': plan['scenario'], 'plan_id': plan['id'], 'input_version': plan['version'],
            'alternative_id': plan['selected_alternative_id'], 'recipient': 'employer', 'format': 'preview'}
    preview = client.post('/api/export', json=body)
    preview.raise_for_status()
    body.update(format='text', preview_id=preview.json()['preview_id'])
    exported = client.post('/api/export', json=body)
    exported.raise_for_status()
    assert exported.text == preview.json()['text']
    assert 'no-store' in exported.headers['cache-control']
    report['checks'].append('Recipient export exactly matches signed preview')
    deleted = client.delete(f"/api/plans/{plan['id']}?expected_version={plan['version']}", headers={'idempotency-key': str(uuid.uuid4())})
    deleted.raise_for_status()
    assert client.get('/api/plans/' + plan['id']).status_code == 404
    report['checks'].append('Deleted test plan is inaccessible')
destination = ROOT / 'docs/evidence' / ('live-api-tls.json' if tls else 'live-api.json')
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
