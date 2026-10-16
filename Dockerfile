FROM python:3.12-slim
WORKDIR /app
# The whole library (1.1 million books) arrives ready-made from the project's GitHub release on start-up,
# into temporary storage (fits Railway's free plan); visitor numbers go to /data, the place for a volume.
# docker-compose keeps the catalogue on its volume too, so it is downloaded only once there.
ENV PYTHONUNBUFFERED=1 \
    DB_URL=https://github.com/aliabbas1111/warraq-fullstack/releases/download/data-v4/warraq-books.db.gz \
    WARRAQ_DB=/app/cache/warraq.db \
    STATS_DB=/data/stats.db \
    FRONTEND_DIR=/app/frontend \
    AUTO_IMPORT=1 \
    IMPORT_LIMIT=0 \
    FORWARDED_ALLOW_IPS=*
# FORWARDED_ALLOW_IPS: the platform's proxy is the only way in, so trust the visitor IP and https it reports
# (without it every visitor looks like the proxy: one IP for the counters and the rate limits)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY frontend ./frontend
# run as an ordinary user, not root: a bug in the app cannot take over the container
RUN useradd --system --uid 10001 --no-create-home warraq && mkdir -p /data /app/cache && chown warraq /data /app/cache
USER warraq
# no VOLUME line: Railway refuses it; attach a volume at /data in the platform (docker-compose declares its own)
EXPOSE 8000
# 1) create tables + seed + one-time imports  2) start the server
# --proxy-headers: the real visitor IP comes from the reverse proxy (set FORWARDED_ALLOW_IPS to trust it)
CMD ["sh", "-c", "python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
