FROM python:3.12-slim
RUN pip install --no-cache-dir mlflow==3.10.1 \
    && useradd --uid 1001 --create-home wathiq \
    && mkdir /mlflow && chown wathiq:wathiq /mlflow
USER wathiq
WORKDIR /mlflow
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=4)"
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/tracking.db", "--default-artifact-root", "/mlflow/artifacts", "--allowed-hosts", "mlflow:5000,localhost:5001,127.0.0.1:5001,localhost:5000"]
