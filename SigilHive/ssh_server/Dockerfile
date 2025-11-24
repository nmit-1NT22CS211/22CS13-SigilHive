FROM python:3.11-slim

# System deps for librdkafka
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    librdkafka-dev \
    netcat-traditional \
    ca-certificates \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only shared modules needed by this service
COPY kafka_manager.py .
COPY kafka_config.json .

# Copy only the ssh server service (excluding secrets and data files)
COPY ssh_server/*.py ./ssh_server/
COPY ssh_server/__init__.py ./ssh_server/

# Copy and prepare entrypoint
COPY ssh_server/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    sed -i 's/\r$//' /usr/local/bin/entrypoint.sh

ENV KAFKA_CONFIG_PATH=.../kafka_config.json
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# Secret will be available at /run/secrets/ssh_host_key
ENV SSH_HOST_KEY_PATH=/run/secrets/ssh_host_key

EXPOSE 5555

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "ssh_server.ssh_server"]