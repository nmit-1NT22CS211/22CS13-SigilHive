FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY http/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY http/ .
COPY rl_core ./rl_core
COPY kafka_manager.py .
COPY file_structure.py .

ENV PORT=8443
EXPOSE 8443

CMD ["python", "http_honeypot.py"]
