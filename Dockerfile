FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Seed the SQLite DB from data/kanji.json at build time so the image is
# self-contained. seed_db.py uses INSERT OR REPLACE + CREATE TABLE IF NOT EXISTS
# so it's idempotent
RUN python scripts/seed_db.py

# Expose port (Render sets PORT env var, default to 8000)
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn server.main:app --host 0.0.0.0 --port ${PORT}
