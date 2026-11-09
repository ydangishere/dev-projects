FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt requirements-graph.txt ./
ARG INSTALL_NEO4J=false
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_NEO4J" = "true" ]; then pip install --no-cache-dir -r requirements-graph.txt; fi && \
    useradd --uid 10001 --create-home checker && mkdir /data && chown checker:checker /data
COPY --chown=checker:checker app app
COPY --chown=checker:checker static static
COPY --chown=checker:checker samples samples
COPY --chown=checker:checker policies policies
USER checker
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--limit-concurrency", "20", "--timeout-keep-alive", "5"]
