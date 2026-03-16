FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install uv && uv sync --package kinship-orchestrator

EXPOSE 8000

CMD ["uv", "run", "--package", "kinship-orchestrator", "python", "-m", "kinship_orchestrator.server", "sse"]
