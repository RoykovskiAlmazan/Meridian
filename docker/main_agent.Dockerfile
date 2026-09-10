FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

# Seguro por defecto (docs/design/0004-sandbox-exec-model.md): mismo endurecimiento que
# los subagentes, no solo ellos -- el main también corre sin privilegios de root.
RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "meridian.main_agent.service"]
