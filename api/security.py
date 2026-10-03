import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request, Response

from api.settings import settings

COOKIE = 'okno_session'
_limits = defaultdict(deque)


def owner_id(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_for(token: str):
    return hmac.new(settings.session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def session_token(request: Request):
    token = request.cookies.get(COOKIE, '')
    if len(token) < 40 or len(token) > 100:
        raise HTTPException(401, 'Sesja wygasła. Odśwież aplikację.')
    return token


def issue_session(request: Request, response: Response):
    token = request.cookies.get(COOKIE, '')
    if not 40 <= len(token) <= 100:
        token = secrets.token_urlsafe(48)
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.secure_cookie,
                        samesite='strict', max_age=60 * 60 * 24 * settings.retention_days)
    return token


def require_owner(request: Request):
    token = session_token(request)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if request.headers.get('origin') != settings.origin:
            raise HTTPException(403, 'Niedozwolone źródło żądania.')
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf_for(token)):
            raise HTTPException(403, 'Odśwież sesję przed zapisaniem zmian.')
    return owner_id(token)


def rate_limit(request: Request):
    key = request.client.host if request.client else 'local'
    now = time.monotonic()
    q = _limits[key]
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= 180:
        raise HTTPException(429, 'Zbyt wiele żądań. Spróbuj za minutę.', headers={'Retry-After': '60'})
    q.append(now)
    if len(_limits) > 10000:
        for k in list(_limits):
            if not _limits[k] or _limits[k][-1] < now - 60:
                del _limits[k]
