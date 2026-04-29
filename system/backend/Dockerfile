FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY manage.py ./
COPY apps ./apps
COPY pqc_ras ./pqc_ras
COPY fixtures ./fixtures
COPY entrypoint.sh /usr/local/bin/crypto-scanner-backend

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir . \
  && chmod +x /usr/local/bin/crypto-scanner-backend

EXPOSE 8000

ENTRYPOINT ["crypto-scanner-backend"]
