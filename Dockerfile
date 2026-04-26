FROM node:18-bullseye

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip3 install -r requirements.txt
RUN npm install -g deepnest-cli

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port $PORT"]
