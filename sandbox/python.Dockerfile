FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.5 ruff==0.11.2 build==1.2.2.post1
USER 65534:65534
WORKDIR /workspace
