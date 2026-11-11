FROM python:3.14-slim AS builder
WORKDIR /build
COPY pyproject.toml .
RUN pip wheel --wheel-dir /wheels .

FROM python:3.14-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY app app
COPY migrations migrations
COPY alembic.ini .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
