FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY adversarial_training/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adversarial_training/ ./adversarial_training/
COPY rl_core/ ./rl_core/
COPY kafka_manager.py .
COPY file_structure.py .

ENV LANGGRAPH_MODE=training
EXPOSE 8000

CMD ["python", "-u", "-m", "adversarial_training.app_integration"]
