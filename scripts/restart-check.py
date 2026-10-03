"""Keep credentials in memory while an operator restarts the deployed API.

Run in a separate client container with a workspace bind mount. The operator
waits for .runtime/restart-ready, restarts API, verifies readiness and creates
.runtime/restart-continue. Both marker files contain no plan data or credentials.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
ready = ROOT / '.runtime/restart-ready'
proceed = ROOT / '.runtime/restart-continue'
base = os.getenv('OKNO_API_URL', 'http://host.docker.internal:18430')
origin = os.getenv('OKNO_ORIGIN', 'http://localhost:18430')
report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'origin': origin,
          'credentials_stored_on_disk': False, 'synthetic_scenario': True}
scenario = json.loads((ROOT / 'data/synthetic/single-parent.json').read_text(encoding='utf-8'))
with httpx.Client(base_url=base, timeout=30) as client:
    session = client.get('/api/session')
    session.raise_for_status()
    client.headers.update({'origin': origin, 'x-csrf-token': session.json()['csrf_token']})
    saved = client.post('/api/plans', json={'scenario': scenario}, headers={'idempotency-key': str(uuid.uuid4())})
    saved.raise_for_status()
    plan = saved.json()
    try:
        ready.write_text('Synthetic plan saved. Restart API, then create restart-continue.\n', encoding='utf-8')
        deadline = time.monotonic() + 120
        while not proceed.exists():
            if time.monotonic() > deadline:
                raise TimeoutError('Operator did not complete the restart within 120 seconds')
            time.sleep(.5)
        received = client.get('/api/plans/' + plan['id'])
        received.raise_for_status()
        restored = received.json()
        assert restored['version'] == plan['version']
        assert restored['scenario'] == plan['scenario']
        assert restored['selected_alternative_id'] == plan['selected_alternative_id']
        report['same_session_read_after_api_restart'] = True
        report['scenario_version_and_selection_preserved'] = True
    finally:
        deleted = client.delete(f"/api/plans/{plan['id']}?expected_version={plan['version']}",
                                headers={'idempotency-key': str(uuid.uuid4())})
        deleted.raise_for_status()
        assert client.get('/api/plans/' + plan['id']).status_code == 404
        report['test_plan_deleted'] = True
        ready.unlink(missing_ok=True)
        proceed.unlink(missing_ok=True)
report['status'] = 'passed'
(ROOT / 'docs/evidence/restart-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
