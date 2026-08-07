FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hyprfeed ./hyprfeed
COPY run.py LICENSE CHANGELOG.md RELEASE_NOTES.md ./

RUN useradd --create-home hyprfeed \
    && mkdir -p /data \
    && chown -R hyprfeed:hyprfeed /data /app
USER hyprfeed

VOLUME /data
EXPOSE 8000

# Single worker + threads: the background refresher runs once, SQLite stays happy.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "90", \
     "--access-logfile", "-", "--bind", "0.0.0.0:8000", "hyprfeed:create_app()"]
