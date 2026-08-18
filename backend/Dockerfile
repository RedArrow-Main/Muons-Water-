FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (psycopg2-binary ships its own libpq; nothing extra needed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Apply migrations + bootstrap on boot (idempotent), then serve.
# PORT is injected by Render.
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
