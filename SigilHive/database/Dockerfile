FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY database/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY database/ .
COPY rl_core ./rl_core
COPY kafka_manager.py .
COPY file_structure.py .

ENV PORT=2224
EXPOSE 2224

CMD ["python", "-u", "database_honeypot.py"]
