FROM python:3.11-slim

WORKDIR /app

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instalar dependencias del sistema para compilar extensiones C y conectar a PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias del proyecto
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Usuario no-root que ejecuta la aplicación
RUN useradd --create-home --uid 1000 appuser

# Copiar el código de la aplicación
COPY --chown=appuser:appuser . .
RUN mkdir -p /app/uploads/documents /app/uploads/images /app/uploads/reports && \
    chown -R appuser:appuser /app /app/uploads

USER appuser

# Exponer el puerto de FastAPI
EXPOSE 8000

# Healthcheck con la librería estándar de Python (no depende de curl)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

# Comando para iniciar el servidor (sin --reload; el modo desarrollo lo añade docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

