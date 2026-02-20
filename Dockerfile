FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# dependencias python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia fuente
COPY . .

EXPOSE 8000

# ⚠️ 1 worker para no matar XAMPP MySQL
CMD ["gunicorn",
     "-w", "1",
     "-k", "gthread",
     "--timeout", "0",
     "--graceful-timeout", "0",
     "--keep-alive", "120",
     "-b", "0.0.0.0:8000",
     "main:app"]