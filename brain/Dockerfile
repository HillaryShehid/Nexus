FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY web_server.py ./
COPY run.py ./

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["python", "web_server.py"]
