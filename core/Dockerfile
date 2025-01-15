FROM python:3.10-slim

WORKDIR /app

COPY core/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "core.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
