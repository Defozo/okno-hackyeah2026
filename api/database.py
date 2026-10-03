import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from api.settings import settings


def utcnow():
    return datetime.now(timezone.utc)


class EncryptedJSON(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return Fernet(settings.encryption_key.encode()).encrypt(json.dumps(value, ensure_ascii=False).encode())

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(Fernet(settings.encryption_key.encode()).decrypt(value))


class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = 'plans'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(EncryptedJSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Operation(Base):
    __tablename__ = 'operations'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(64), index=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    response: Mapped[dict] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Tombstone(Base):
    __tablename__ = 'tombstones'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExportSnapshot(Base):
    __tablename__ = 'export_snapshots'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey('plans.id', ondelete='CASCADE'), index=True)
    payload: Mapped[dict] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


if settings.database_url.startswith('sqlite'):
    Path('.runtime').mkdir(exist_ok=True)
engine = create_engine(settings.database_url, pool_pre_ping=True,
                       connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {})
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
