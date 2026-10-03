"""Explicit operator retention, encrypted backup and deletion-aware restore CLI."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy import select, delete
from api.database import SessionLocal, Plan, Operation, Tombstone, ExportSnapshot, utcnow
from api.settings import settings
from api.plans import reset_source_claims


def purge(db, now=None):
    now = now or utcnow()
    cutoff = now - timedelta(days=settings.retention_days)
    ids = list(db.scalars(select(Plan.id).where(Plan.updated_at < cutoff)))
    for plan_id in ids:
        if not db.get(Tombstone, plan_id):
            db.add(Tombstone(id=plan_id))
        db.execute(delete(ExportSnapshot).where(ExportSnapshot.plan_id == plan_id))
        for op in db.scalars(select(Operation).where(Operation.plan_id == plan_id)):
            op.response = {'deleted': True}
        db.execute(delete(Plan).where(Plan.id == plan_id))
    db.execute(delete(Operation).where(Operation.created_at < cutoff))
    db.commit()
    return len(ids)


def create_backup(db, directory):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {'schema_version': 1, 'created_at': utcnow().isoformat(),
               'tombstones': [t.id for t in db.scalars(select(Tombstone))],
               'plans': [{'id': p.id, 'owner': p.owner, 'version': p.version, 'updated_at': p.updated_at.isoformat(), 'payload': p.payload} for p in db.scalars(select(Plan))]}
    path = directory / (utcnow().strftime('%Y%m%dT%H%M%SZ') + '.okno.enc')
    path.write_bytes(Fernet(settings.encryption_key.encode()).encrypt(json.dumps(payload).encode()))
    for old in directory.glob('*.okno.enc'):
        if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < utcnow() - timedelta(days=settings.backup_retention_days):
            old.unlink()
    return path


def restore(db, path):
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('Backup exceeds operator restore limit')
    payload = json.loads(Fernet(settings.encryption_key.encode()).decrypt(path.read_bytes()))
    if payload.get('schema_version') != 1:
        raise ValueError('Unsupported backup schema')
    deleted = set(db.scalars(select(Tombstone.id))) | set(payload['tombstones'])
    restored = 0
    for item in payload['plans']:
        if item['id'] in deleted or db.get(Plan, item['id']):
            continue
        state = item['payload']
        reset_source_claims(state['scenario'])
        state['result'] = {'status': 'UNKNOWN', 'data_status': 'needs_input', 'alternatives': [],
                           'data_gaps': [{'code': 'restored_backup', 'message': 'Odtworzona kopia wymaga sprawdzenia danych i ponownego obliczenia.'}]}
        for decision in state.get('decisions', []):
            decision['restored'] = True
        if state.get('trial'):
            state['trial']['scenario_hash'] = 'restored_requires_reassessment'
        db.add(Plan(id=item['id'], owner=item['owner'], version=item['version'] + 1, payload=state,
                    updated_at=datetime.fromisoformat(item['updated_at'])))
        restored += 1
    for plan_id in deleted:
        if not db.get(Tombstone, plan_id):
            db.add(Tombstone(id=plan_id))
        db.execute(delete(Plan).where(Plan.id == plan_id))
        db.execute(delete(ExportSnapshot).where(ExportSnapshot.plan_id == plan_id))
    db.commit()
    return restored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['purge', 'backup', 'restore'])
    parser.add_argument('--path', default='.runtime/backups')
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == 'purge':
            print(json.dumps({'purged': purge(db)}))
        elif args.command == 'backup':
            print(json.dumps({'backup': str(create_backup(db, Path(args.path)))}))
        else:
            print(json.dumps({'restored': restore(db, Path(args.path))}))


if __name__ == '__main__':
    main()
