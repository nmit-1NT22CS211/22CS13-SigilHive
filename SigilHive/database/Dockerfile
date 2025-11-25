FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=2224
EXPOSE 2224

CMD ["python", "-u", "database_honeypot.py"]
