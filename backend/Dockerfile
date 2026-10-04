FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# PORT is injected by Render (and most PaaS hosts); 8000 stays the default for
# docker-compose. --forwarded-allow-ips '*' makes uvicorn trust the
# X-Forwarded-For header from the host's proxy — without it every request
# appears to come from the proxy's IP and the per-IP login rate limiter
# (app/core/rate_limit.py) would throttle all users as one. Only safe because
# the container is reachable solely through that proxy.
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
