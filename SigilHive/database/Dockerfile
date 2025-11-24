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

# Copy only the database service
COPY database/ ./database/

# Copy and prepare entrypoint
COPY database/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    sed -i 's/\r$//' /usr/local/bin/entrypoint.sh

ENV KAFKA_CONFIG_PATH=/app/kafka_config.json
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 2222

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "database.database_honeypot"]