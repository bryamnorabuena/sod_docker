FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

# dependencias python
COPY requirements.txt /app/requirements.txt

# (opcional) Actualiza pip/setuptools/wheel para evitar issues de build
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -r /app/requirements.txt


# # Asegurar carpeta para el CA del MySQL (si usas secret volume)
RUN mkdir -p /app/certs
RUN cp /app/db/DigiCertGlobalRootG2.crt.pem /app/certs/mysql-ca-cert

EXPOSE 8000

CMD ["gunicorn", "-w", "1", "-k", "gthread", "--timeout", "0", "--graceful-timeout", "0", "--keep-alive", "120", "-b", "0.0.0.0:8000", "main:app"]