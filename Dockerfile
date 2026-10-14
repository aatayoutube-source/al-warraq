FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    WARRAQ_DB=/data/warraq.db \
    FRONTEND_DIR=/app/frontend \
    AUTO_IMPORT=1 \
    IMPORT_LIMIT=0
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY frontend ./frontend
# run as an ordinary user, not root: a bug in the app cannot take over the container
RUN useradd --system --uid 10001 --no-create-home warraq && mkdir -p /data && chown warraq /data
USER warraq
EXPOSE 8000
# 1) create tables + seed + one-time imports  2) start the server
# --proxy-headers: the real visitor IP comes from the reverse proxy (set FORWARDED_ALLOW_IPS to trust it)
CMD ["sh", "-c", "python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
