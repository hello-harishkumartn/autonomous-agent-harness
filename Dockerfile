FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends docker.io git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]"
RUN useradd --create-home --uid 10001 adev && mkdir -p /state /repositories && chown -R adev:adev /state /repositories
USER adev
ENV ADEV_STATE_DIR=/state
EXPOSE 8000
CMD ["uvicorn", "autonomousdev.api:app", "--host", "0.0.0.0", "--port", "8000"]
