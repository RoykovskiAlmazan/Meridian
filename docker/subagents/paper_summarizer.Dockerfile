FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "meridian.subagents.paper_summarizer.main"]
