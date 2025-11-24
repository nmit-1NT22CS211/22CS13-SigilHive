FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=2223
EXPOSE 2223

CMD ["python", "ssh_server.py"]
