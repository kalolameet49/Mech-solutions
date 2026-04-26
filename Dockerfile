FROM python:3.11-slim

WORKDIR /app

COPY . .

# Install Python deps
RUN pip install -r requirements.txt

# Start API
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
