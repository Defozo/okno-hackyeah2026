import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet

_test_directory = tempfile.TemporaryDirectory(prefix='okno-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_test_directory.name) / 'test.db').replace('\\', '/')
os.environ['OKNO_SESSION_SECRET'] = 'test-only-session-secret-never-deploy-' + 'a' * 32
os.environ['OKNO_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
os.environ['APP_ORIGIN'] = 'http://testserver'
os.environ['COOKIE_SECURE'] = 'false'


def pytest_sessionfinish(session, exitstatus):
    from api.database import engine
    engine.dispose()
    _test_directory.cleanup()
