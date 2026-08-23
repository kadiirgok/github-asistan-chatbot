FROM python:3.12-slim

WORKDIR /app

# Derleme gerektiren bağımlılıklar (hnswlib vb.) için gcc/g++.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=7860
EXPOSE 7860

CMD uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-7860}
