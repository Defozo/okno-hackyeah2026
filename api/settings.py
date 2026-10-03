import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///.runtime/okno.db')
    origin: str = os.getenv('APP_ORIGIN', 'http://localhost:18430')
    session_secret: str = os.getenv('OKNO_SESSION_SECRET', '')
    encryption_key: str = os.getenv('OKNO_ENCRYPTION_KEY', '')
    secure_cookie: bool = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
    data_mode: str = os.getenv('DATA_MODE', 'synthetic')
    routing_mode: str = os.getenv('ROUTING_MODE', 'manual')
    solver_budget: float = float(os.getenv('SOLVER_TOTAL_BUDGET_SECONDS', '20'))
    solver_workers: int = int(os.getenv('SOLVER_MAX_CONCURRENT', '2'))
    retention_days: int = int(os.getenv('PLAN_RETENTION_DAYS', '30'))
    backup_retention_days: int = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))


settings = Settings()
