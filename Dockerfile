# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

ARG INSTALL_TREASURY_ANALYTICS_MOCK=false
ARG TREASURY_ANALYTICS_PACKAGE=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system sipm \
    && useradd --system --gid sipm --home-dir /app --shell /usr/sbin/nologin sipm

COPY requirements.txt /tmp/requirements.txt
COPY deployment/mock-packages/treasury_analytics /tmp/treasury_analytics_mock
RUN --mount=type=secret,id=pip_extra_index_url,required=false \
    pip_extra_index_url_file="/run/secrets/pip_extra_index_url" \
    && if [ -s "${pip_extra_index_url_file}" ]; then \
        export PIP_EXTRA_INDEX_URL="$(cat "${pip_extra_index_url_file}")"; \
    fi \
    && pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && if [ "${INSTALL_TREASURY_ANALYTICS_MOCK}" = "true" ] && [ -n "${TREASURY_ANALYTICS_PACKAGE}" ]; then \
        echo "Choose either INSTALL_TREASURY_ANALYTICS_MOCK=true or TREASURY_ANALYTICS_PACKAGE, not both." >&2; \
        exit 1; \
    elif [ "${INSTALL_TREASURY_ANALYTICS_MOCK}" = "true" ]; then \
        pip install /tmp/treasury_analytics_mock; \
    elif [ -n "${TREASURY_ANALYTICS_PACKAGE}" ]; then \
        pip install "${TREASURY_ANALYTICS_PACKAGE}"; \
    fi \
    && rm -rf /tmp/treasury_analytics_mock

COPY src/main/backend /app/backend
COPY src/main/ui /app/ui
COPY docs/sql /app/docs/sql

RUN mkdir -p /app/data/external_docs \
    && chown -R sipm:sipm /app

USER sipm

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT}"]
