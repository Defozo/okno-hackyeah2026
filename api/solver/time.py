"""Calendar expansion shared by normalization, never by constraint validation."""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo
from api.domain import CalendarRule, Source

WARSAW = ZoneInfo("Europe/Warsaw")


@lru_cache(maxsize=2048)
def clock_minutes(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(x.isdigit() for x in parts):
        raise ValueError(f"Nieprawidłowa godzina: {value}")
    h, m = map(int, parts)
    if not 0 <= h <= 24 or not 0 <= m < 60 or (h == 24 and m != 0):
        raise ValueError(f"Nieprawidłowa godzina: {value}")
    return h * 60 + m


def format_clock(value: int) -> str:
    return f"{(value // 60) % 24:02d}:{value % 60:02d}"


@lru_cache(maxsize=100_000)
def local_minute(day: date, value: str, fold: int | None = None) -> int:
    naive = datetime.combine(day, datetime.min.time()) + timedelta(minutes=clock_minutes(value))
    candidates = []
    for f in (0, 1):
        aware = naive.replace(tzinfo=WARSAW, fold=f)
        if aware.astimezone(timezone.utc).astimezone(WARSAW).replace(tzinfo=None) == naive:
            candidates.append((f, int(aware.timestamp() // 60)))
    unique = {m for _, m in candidates}
    if not unique:
        raise ValueError(f"Godzina {day} {value} nie istnieje przy zmianie czasu")
    if len(unique) > 1 and fold is None:
        raise ValueError(f"Godzina {day} {value} występuje dwukrotnie; wybierz start_fold/end_fold 0 lub 1")
    for f, minute in candidates:
        if fold is None or fold == f:
            return minute
    raise ValueError("Nieprawidłowy wybór powtórzonej godziny")


@lru_cache(maxsize=100_000)
def iso(minute: int) -> str:
    return datetime.fromtimestamp(minute * 60, WARSAW).isoformat(timespec="minutes")


def matches(rule: CalendarRule, day: date) -> bool:
    return (day not in rule.excluded_dates and
            (not rule.valid_from or day >= rule.valid_from) and
            (not rule.valid_to or day <= rule.valid_to) and
            (day in rule.dates if rule.dates else day.weekday() in rule.weekdays))


def days_between(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def fresh(source: Source, day: date) -> bool:
    return (source.status == "current" and (source.valid_from is None or day >= source.valid_from)
            and (source.valid_to is None or day <= source.valid_to))


def window(day, start, end, start_fold=None, end_fold=None):
    first = local_minute(day, start, start_fold)
    end_day = day + timedelta(days=1) if clock_minutes(end) <= clock_minutes(start) else day
    return first, local_minute(end_day, end, end_fold)
