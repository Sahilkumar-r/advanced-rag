# Hugging Face Space (Docker SDK, port 7860) or any container host. Secrets are never baked in: they are supplied at run time.
# The docs come from the build context (data/raw, fetched at the commits pinned in eval/datasets/docs.lock.json by scripts/fetch_docs.py),
# so building needs PyPI and the embedding model download, and nothing else. Run `python scripts/fetch_docs.py` before `docker build`.
FROM python:3.12-slim
# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 FASTEMBED_CACHE_PATH=/app/.cache/fastembed PORT=7860 RAGX_HOST=0.0.0.0
COPY pyproject.toml ./
COPY src ./src
RUN pip install .
COPY web ./web
COPY scripts/serve.py scripts/seed_users.py scripts/prebuild.py scripts/space_entry.py ./scripts/
COPY eval/results ./eval/results
COPY data/raw ./data/raw
COPY NOTICE.md LICENSE ./
RUN mkdir -p data/state data/index .cache && chown -R user:user /app
USER user
# Download the embedding model and embed the chunks now, so the first request after a cold start is not waiting on either.
RUN python scripts/prebuild.py
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=4).status == 200 else 1)"
CMD ["python", "scripts/space_entry.py"]
