from copy import deepcopy
import json
from datetime import timedelta
from pathlib import Path
from api.database import Base, engine, SessionLocal, Plan, Tombstone, utcnow
from api.maintenance import create_backup, restore, purge
from api.plans import new_plan, serialize_plan


def test_backup_encrypted_and_restore_respects_deletion(tmp_path):
    Base.metadata.create_all(engine)
    scenario = json.loads(Path('data/synthetic/single-parent.json').read_text(encoding='utf-8'))
    scenario['notes'] = 'NOT-IN-BACKUP-PLAINTEXT'
    with SessionLocal() as db:
        plan = new_plan('test-maintenance-owner', scenario, {'alternatives': []})
        db.add(plan)
        db.commit()
        path = create_backup(db, tmp_path)
        assert b'NOT-IN-BACKUP-PLAINTEXT' not in path.read_bytes()
        plan_id = plan.id
        db.delete(plan)
        db.add(Tombstone(id=plan_id))
        db.commit()
        restore(db, path)
        assert db.get(Plan, plan_id) is None


def test_retention_removes_expired_plan(tmp_path):
    Base.metadata.create_all(engine)
    scenario = json.loads(Path('data/synthetic/single-parent.json').read_text(encoding='utf-8'))
    with SessionLocal() as db:
        plan = new_plan('test-expired-owner', scenario, {'alternatives': []})
        plan.updated_at = utcnow() - timedelta(days=31)
        db.add(plan)
        db.commit()
        plan_id = plan.id
        assert purge(db) >= 1
        assert db.get(Plan, plan_id) is None
        assert db.get(Tombstone, plan_id)


def test_operator_restore_rechecks_resource_and_handoff_claims(tmp_path):
    Base.metadata.create_all(engine)
    scenario = json.loads(Path('data/synthetic/care-handoff.json').read_text(encoding='utf-8'))
    from api.solver import solve_scenario
    with SessionLocal() as db:
        plan = new_plan('restore-check', scenario, solve_scenario(scenario))
        db.add(plan)
        db.commit()
        plan_id = plan.id
        path = create_backup(db, tmp_path)
        # Simulated database loss, distinct from intentional deletion.
        db.delete(plan)
        db.commit()
        restore(db, path)
        restored = serialize_plan(db.get(Plan, plan_id))
        assert restored['status'] != 'confirmed'
        assert restored['result']['data_status'] == 'needs_input'
        assert all(not r['confirmed'] for r in restored['scenario']['care_resources'])
        assert not restored['scenario']['care_needs'][0]['arrangements'][0]['handoffs'][0]['confirmed']
