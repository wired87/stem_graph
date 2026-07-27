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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cnvmaster ./cnvmaster
COPY product ./product
COPY file_master ./file
COPY infrastructure ./infrastructure
COPY user ./user
COPY manage.py main.py ./

EXPOSE 8000

CMD ["python", "main.py"]
