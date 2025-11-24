FROM python:3.11-slim

# System deps for librdkafka
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    librdkafka-dev \
    netcat-traditional \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only shared modules needed by this service
COPY kafka_manager.py .
COPY kafka_config.json .

# Copy only the http honeypot service (excluding secrets)
COPY http_honeypot_service/*.py ./http_honeypot_service/
COPY http_honeypot_service/__init__.py ./http_honeypot_service/

# Copy and prepare entrypoint
COPY http_honeypot_service/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    sed -i 's/\r$//' /usr/local/bin/entrypoint.sh


ENV KAFKA_CONFIG_PATH=/app/kafka_config.json
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# Secrets will be available at /run/secrets/shophub_cert and /run/secrets/shophub_key
ENV TLS_CERT_PATH=./shophub_cert.pem
ENV TLS_KEY_PATH=./shophub_key.pem

EXPOSE 8443

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "http_honeypot_service.http_honeypot"]