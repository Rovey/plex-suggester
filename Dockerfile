FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

FROM python:3.11-slim

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/plex-suggest /usr/local/bin/plex-suggest
COPY src/ src/

ENV DATA_DIR=/data
EXPOSE 8000

USER appuser
CMD ["plex-suggest", "server", "--host", "0.0.0.0", "--port", "8000"]
