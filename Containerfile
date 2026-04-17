FROM python:3.13-alpine

RUN adduser -D appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

USER appuser

ENTRYPOINT ["python", "server.py"]
