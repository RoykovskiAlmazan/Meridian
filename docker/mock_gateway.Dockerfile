FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["uvicorn", "meridian.gateways.mock_gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
