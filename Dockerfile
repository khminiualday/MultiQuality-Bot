FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_mtproto.py .

RUN mkdir -p /app/work /app/session
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot_mtproto.py"]
