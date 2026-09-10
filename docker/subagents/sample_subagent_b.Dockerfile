FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

# Sandbox por defecto (docs/design/0004-sandbox-exec-model.md): el subagente corre sin
# privilegios de root; la red y las capabilities se restringen desde docker-compose.yml.
RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "meridian.subagents.sample_subagent_b.main"]
