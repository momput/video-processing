FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    apt-get update && apt-get install -y --no-install-recommends gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

ENV PYTHONPATH=/app

CMD ["python", "/app/main.py"]