FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home taskhub
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=taskhub:taskhub app ./app
COPY --chown=taskhub:taskhub migrations ./migrations
COPY --chown=taskhub:taskhub alembic.ini .
USER taskhub
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
