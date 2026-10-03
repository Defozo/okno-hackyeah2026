FROM node:24.13.0-bookworm-slim AS web
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12.9-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/opt/browsers PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt && python -m playwright install --with-deps chromium
COPY api/ ./api/
COPY data/ ./data/
COPY scripts/entrypoint.py ./scripts/entrypoint.py
COPY scripts/maintenance_loop.py ./scripts/maintenance_loop.py
COPY alembic.ini ./
COPY --from=web /build/web/dist ./web/dist
RUN useradd --create-home --uid 10001 okno && mkdir /app/.runtime /app/backups && chown okno:okno /app/.runtime /app/backups
USER okno
EXPOSE 8000
ENTRYPOINT ["python", "scripts/entrypoint.py"]
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--workers", "1"]
