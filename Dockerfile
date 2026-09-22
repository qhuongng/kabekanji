FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose port (Render sets PORT env var, default to 8000)
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn server.main:app --host 0.0.0.0 --port ${PORT}
