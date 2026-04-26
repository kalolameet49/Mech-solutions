FROM node:18-bullseye

RUN apt-get update && apt-get install -y \
    python3 python3-pip build-essential

WORKDIR /app

COPY . .

RUN pip3 install -r requirements.txt
RUN npm install -g deepnest-cli

EXPOSE 8501 8000

CMD bash start.sh
