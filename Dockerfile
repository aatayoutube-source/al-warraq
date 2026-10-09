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
RUN mkdir -p /data
VOLUME /data
EXPOSE 8000
# 1) create tables + seed + one-time Gutenberg import  2) start the server
CMD ["sh", "-c", "python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
