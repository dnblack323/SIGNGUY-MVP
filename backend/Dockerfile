# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/pricing_engine_package.lock.json ./pricing_engine_package.lock.json
COPY backend/scripts/install_pricing_engine.py ./scripts/install_pricing_engine.py
RUN --mount=type=secret,id=pricing_engine_read_token,required=true \
    PRICING_ENGINE_READ_TOKEN="$(cat /run/secrets/pricing_engine_read_token)" \
    python scripts/install_pricing_engine.py

COPY backend/ ./

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
