FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]
