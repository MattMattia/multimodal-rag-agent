FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias mínimas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Usuario no-root que ejecuta la aplicación
RUN useradd --create-home --uid 1000 appuser

# Copiar el código de la aplicación
COPY --chown=appuser:appuser . .
RUN chown -R appuser:appuser /app

USER appuser

# Exponer el puerto por defecto de Streamlit
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando de arranque de la aplicación Streamlit
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]

