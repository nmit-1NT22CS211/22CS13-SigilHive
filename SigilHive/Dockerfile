FROM python:3.11-slim

WORKDIR /app

COPY sequential_attack_runner.py .

RUN pip install --no-cache-dir asyncssh langchain_google_genai langchain-core langgraph dotenv

CMD ["python", "sequential_attack_runner.py"]