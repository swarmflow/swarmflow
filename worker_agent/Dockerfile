FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y wget

COPY worker_agent/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002
