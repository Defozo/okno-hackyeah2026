"""Civil dates used by consent, observations and public-source validity."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo('Europe/Warsaw')


def warsaw_today(now: datetime | None = None) -> date:
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Calendar clock requires an aware instant')
    return instant.astimezone(WARSAW).date()
