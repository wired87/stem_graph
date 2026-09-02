# CNVMaster DRF API image — serves Django REST framework via main.py
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=cnvmaster.settings
ENV PYTHONPATH=/app:/app/user
ENV ALLOWED_HOSTS=*
ENV DJANGO_HOST=0.0.0.0
ENV DJANGO_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends docker.io ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
