#!/usr/bin/env python3
import requests

url = 'https://prometheus-prod-43-prod-ap-south-1.grafana.net/api/prom/push'
user = '2822379'
token = 'glc_eyJvIjoiMTU5OTMxMSIsIm4iOiJzdGFjay0xNDQ5MDczLWhtLXdyaXRlLWZsYW1lZ2lhbnQiLCJrIjoiVnZxbVFsMTQ3MDlsVzNZNjgzWUpUZnI3IiwibSI6eyJyIjoicHJvZC1hcC1zb3V0aC0xIn19'

payloads = [
    'sigilhive_http_attacks 10\nsigilhive_ssh_attacks 5\nsigilhive_db_attacks 3',
    'sigilhive_http_attacks{job="honeypot"} 10',
]

for i, payload in enumerate(payloads):
    try:
        r = requests.post(url, data=payload, auth=(user, token), headers={'Content-Type': 'text/plain'})
        print(f'Payload {i}: Status {r.status_code}')
        if r.status_code >= 400:
            print(f'  Response: {r.text[:100]}')
    except Exception as e:
        print(f'Payload {i}: Error {str(e)[:100]}')
