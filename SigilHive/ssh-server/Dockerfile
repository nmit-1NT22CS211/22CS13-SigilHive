FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5555
EXPOSE 5555

CMD ["python", "-u", "ssh_server.py"]
