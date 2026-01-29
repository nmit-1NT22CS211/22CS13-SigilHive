FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY ssh_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ssh_server/ .
COPY rl_core ./rl_core
COPY kafka_manager.py .
COPY file_structure.py .

ENV PORT=5555
EXPOSE 5555

CMD ["python", "-u", "ssh_server.py"]

