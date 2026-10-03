"""Map only injected credentials to the role-specific DB URL, never print it."""
import os
import subprocess
import sys
from urllib.parse import quote

role = os.getenv('DB_ROLE', 'okno_app')
password_key = 'OKNO_DB_MIGRATOR_PASSWORD' if role == 'okno_migrator' else 'OKNO_DB_APP_PASSWORD'
os.environ['DATABASE_URL'] = f"postgresql+psycopg://{role}:{quote(os.environ[password_key], safe='')}@db:5432/okno"
os.execvp(sys.argv[1], sys.argv[1:])
