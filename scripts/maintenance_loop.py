import time
from pathlib import Path
from api.database import SessionLocal
from api.maintenance import create_backup, purge

while True:
    try:
        with SessionLocal() as db:
            count = purge(db)
            create_backup(db, Path('/app/backups'))
            print(f'Maintenance completed; expired plans removed: {count}', flush=True)
    except Exception:
        # Do not log SQL parameters, ciphertext, requests or private payloads.
        print('Maintenance failed; operator inspection required.', flush=True)
    time.sleep(86400)
