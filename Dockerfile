FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN python -m pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system taskhub \
    && useradd --system --gid taskhub --create-home taskhub

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN python -m pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY alembic ./alembic
COPY alembic.ini .
COPY app ./app
COPY docker/entrypoint.sh /usr/local/bin/taskhub-entrypoint
RUN chmod +x /usr/local/bin/taskhub-entrypoint \
    && chown -R taskhub:taskhub /app

USER taskhub
EXPOSE 8000

ENTRYPOINT ["taskhub-entrypoint"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
