FROM python:3.12-slim

WORKDIR /app

# Bağımlılıkları önce kopyala/indir (katman önbelleği için).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala (.dockerignore sayesinde .env/models/chroma_db hariç).
COPY . .

# Hugging Face Spaces 7860 portunda dinler.
ENV PORT=7860
EXPOSE 7860

CMD uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-7860}
