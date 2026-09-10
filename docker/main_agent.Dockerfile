FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

CMD ["python", "-m", "meridian.main_agent.service"]
