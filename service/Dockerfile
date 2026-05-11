FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY . .

RUN uv sync --package kinship-service

EXPOSE 8000

CMD ["uv", "run", "--package", "kinship-service", "uvicorn", "kinship_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
