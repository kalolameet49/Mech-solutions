FROM node:18-bullseye

# Install Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# Install Python deps
RUN pip3 install -r requirements.txt

# Install Deepnest CLI
RUN npm install -g deepnest-cli

# Start API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
