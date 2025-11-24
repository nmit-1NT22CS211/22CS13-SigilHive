FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8443
EXPOSE 8443

CMD ["python", "http_honeypot.py"]
