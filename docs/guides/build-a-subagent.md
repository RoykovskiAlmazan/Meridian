# Guía: construir un subagente real de punta a punta

Meridian no asume ningún dominio -- tú decides qué hace tu subagente escribiendo código
Python normal (organizar archivos, vigilar un feed, resumir correos, revisar inventario,
lo que sea); el resto (colas, seguridad, permisos, programación) ya lo resuelve la
plataforma. Esta guía recorre ese proceso completo, de principio a fin.

Antes de empezar, ten Meridian instalado y sano: `meridianctl doctor` debe salir en
verde (ver [README.md](../../README.md) si todavía no llegaste ahí).

## El mapa mental

```
 cron (o cualquier gateway) --intent--> main --(si hay permiso)--> tu subagente
                                          |                              |
                                          `-------- fan-in <-------------'
                                                       |
                                                       v
                                          resultado en el stream de Redis
                                          del gateway (`meridianctl results tail`)
```

Un **gateway** dispara instrucciones (`TaskIntent`). **`main`** decide si el gateway tiene
permiso para pedirle algo a tu subagente (allowlist explícita) y si la policy del
subagente exige aprobación humana antes de ejecutar. Tu **subagente** es un proceso que
escucha su propia cola, corre tu función `handle(payload)`, y devuelve un resultado
(`TaskResult`). Nada de esto cambia según el dominio -- lo único tuyo es `handle`.

---

## 1. Escribe la lógica (el único código que es "tuyo")

Un subagente mínimo es un módulo con una función `handle(payload: dict) -> dict` y un
`main()` que lo conecta al loop genérico:

```python
# src/meridian/subagents/mi_subagente/main.py
import os
import sys
from typing import Any

from meridian.subagents.worker_base import run


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    # tu lógica aquí -- payload es lo que venga en intent.payload
    return {"resultado": "lo que sea que calculaste"}


def main() -> None:
    subagent_id = os.environ.get("SUBAGENT_ID")
    if not subagent_id:
        print("Falta SUBAGENT_ID en el entorno", file=sys.stderr)
        raise SystemExit(1)
    run(subagent_id, handle)


if __name__ == "__main__":
    main()
```

No olvides el `src/meridian/subagents/mi_subagente/__init__.py` (vacío, solo para que sea
un paquete). Si necesitas llamar a una API externa, escribe tu propio cliente HTTP en un
módulo aparte (ver `src/meridian/subagents/arxiv_client.py` como referencia de estilo) --
no hay que meter nada de eso en la plataforma, vive enteramente en tu subagente.

Si tu subagente puede generar texto con un LLM, hazlo opcional y que se degrade solo (ver
sección 6): revisa si tiene un proveedor configurado (`get_provider_for_subagent`) y, si
no, cae a un resultado más simple. Meridian nunca debería dejar de funcionar solo porque
no hay un LLM configurado.

### Errores: no los captures tú

`worker_base.run` ya envuelve tu `handle` en un try/except -- si algo truena, se publica
un `TaskResult` con `status: "error"` en vez de crashear el subagente. No necesitas tu
propio manejo de errores salvo que quieras un mensaje más específico.

---

## 2. Empaquétalo (Dockerfile)

Copia el patrón que ya usan todos los subagentes -- imagen slim, usuario no-root:

```dockerfile
# docker/subagents/mi_subagente.Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY schemas ./schemas

RUN pip install --no-cache-dir .

RUN useradd --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "meridian.subagents.mi_subagente.main"]
```

---

## 3. Dale un contenedor en `docker-compose.yml`

Agrega un servicio nuevo bajo un profile propio (así no se levanta con
`meridianctl dev up` normal, solo cuando alguien lo pide explícitamente), con una IP fija
en `meridian_internal` y el mismo hardening que todos los demás subagentes:

```yaml
  mi_subagente:
    profiles: ["mi-profile"]
    build:
      context: ..
      dockerfile: docker/subagents/mi_subagente.Dockerfile
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
      SUBAGENT_ID: ${MI_SUBAGENTE_SUBAGENT_ID:-}
      HTTP_PROXY: http://egress_proxy:3128
      HTTPS_PROXY: http://egress_proxy:3128
      NO_PROXY: postgres,redis,vault,localhost,127.0.0.1
      no_proxy: postgres,redis,vault,localhost,127.0.0.1
      PYTHONDONTWRITEBYTECODE: "1"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      meridian_internal:
        ipv4_address: 172.28.1.14   # siguiente IP libre -- revisa las que ya están usadas en el archivo
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
```

Busca la IP más alta que ya esté en uso en `docker-compose.yml` (`172.28.1.x`) y usa la
siguiente libre.

---

## 4. Dale salida a internet (si la necesita) -- `squid.conf`

Por defecto **ningún** subagente tiene salida a internet. Si el tuyo llama a una API
externa, agrega su IP fija y el dominio exacto que necesita en
[`docker/sandbox/squid.conf`](../../docker/sandbox/squid.conf), **antes** del
`http_access deny all` final:

```
# ---- mi_subagente (172.28.1.14) ----
acl subagent_mi_subagente src 172.28.1.14/32
acl subagent_mi_subagente_allowed_domains dstdomain .api-que-necesites.com

http_access allow subagent_mi_subagente subagent_mi_subagente_allowed_domains
```

No agregues más dominios de los que de verdad usa -- si más adelante le conectas un LLM,
agrega también el dominio de ese proveedor (`.anthropic.com`, `.openai.com`, etc.) en ese
momento, no antes.

---

## 5. Dale identidad y permisos (`meridianctl`)

Con el código y el contenedor listos, ahora la parte que no es código -- dar de alta las
identidades y conectarlas. Todo esto es reversible y no requiere reconstruir nada.

```bash
# 1. Un tenant (o reusa uno que ya tengas -- usa uno nuevo si quieres aislar este caso
#    de uso de otros que ya tengas corriendo: los datos, allowlists y policies nunca
#    cruzan tenants)
meridianctl tenant create --name mi-organizacion

# 2. Un gateway -- aquí cron, para que se dispare solo cada cierto tiempo
meridianctl gateway create --tenant <tenant_id> --type cron --name mi-cron

# 3. El subagente (la identidad en Postgres -- el código ya lo escribiste en el paso 1)
meridianctl subagent create --tenant <tenant_id> --name mi-subagente --domain lo-que-sea

# 4. Permiso explícito: sin esto, main rechaza el intent aunque todo lo demás exista
meridianctl allow set --gateway <gateway_id> --subagent <subagent_id> --intents mi_dominio.mi_accion

# 5. (Opcional pero recomendado si es de solo lectura) policy permisiva -- por default
#    un subagente nuevo requiere aprobación humana para TODO (conservador a propósito)
cat > policy.json <<'EOF'
{
  "schema_version": "1.0",
  "requires_approval_intents": [],
  "destructive": { "allowed": false, "requires_approval": true }
}
EOF
meridianctl policy set --subagent <subagent_id> --file policy.json

# 6. El job programado
meridianctl cron create --tenant <tenant_id> --gateway <gateway_id> \
  --name mi-job --schedule "@hourly" --intent-type mi_dominio.mi_accion \
  --subagents <subagent_id> --payload '{"lo":"que necesite tu handle"}'

# 7. Levantar el contenedor (agrega MI_SUBAGENTE_SUBAGENT_ID=<subagent_id> a tu .env primero)
docker compose --env-file .env -f docker/docker-compose.yml --profile mi-profile up -d --build mi_subagente
```

Anota bien los ids que te va imprimiendo cada comando (`tenant_id`, `gateway_id`,
`subagent_id`) -- los vas a necesitar en los pasos siguientes.

---

## 6. Conéctale un LLM (opcional)

Si tu `handle` usa `meridian.llm.registry.get_provider_for_subagent` para generar texto,
conecta un proveedor real:

```bash
meridianctl secrets put --path llm/anthropic --field api_key   # prompt oculto
meridianctl llm set --subagent <subagent_id> --provider anthropic \
  --model claude-sonnet-5 --credential-ref vault:secret/llm/anthropic#api_key
meridianctl llm test --subagent <subagent_id>   # llamada real, confirma que funciona
```

Tu subagente debe seguir funcionando sin esto -- solo con un resultado más simple (ver
`paper_summarizer/main.py` como referencia de ese patrón de "degradar, no fallar": cae a
un resumen extractivo si no hay LLM configurado).

---

## 7. Pruébalo sin esperar al reloj

Si tu schedule es `@hourly` o algo largo, no vas a querer esperar para ver si funciona.
El truco: deshabilita el job real un momento, crea uno de prueba con un intervalo corto,
confírmalo, y revierte:

```bash
meridianctl cron disable --id <real_job_id>
meridianctl cron create --tenant <tenant_id> --gateway <gateway_id> \
  --name mi-job-TEST --schedule "*/2 * * * *" --intent-type mi_dominio.mi_accion \
  --subagents <subagent_id> --payload '{"...":"..."}'
# espera ~2 minutos
meridianctl cron disable --id <test_job_id>
meridianctl cron enable --id <real_job_id>
```

`@hourly` solo dispara en el tope de la hora (`_is_due` en `cron_gateway/service.py`
calcula el siguiente disparo desde `last_run_at`/`created_at`) -- no hay forma de
"forzarlo" sin bajar el intervalo momentáneamente como arriba, o esperar de verdad.

---

## 8. Ve el resultado real

`meridianctl audit tail` solo te dice si salió bien o mal (es un rastro de auditoría, no
guarda el contenido). Para ver lo que tu subagente realmente contestó:

```bash
meridianctl results tail --gateway <gateway_id>
```

Esto lee directo el stream de resultados del gateway y te lo muestra formateado --
`output` completo, `error` si falló, y timestamps.

---

## 9. Cuando termines de probar

Si no vas a usarlo por un rato, apaga el cron (no borra nada, solo detiene los disparos)
y baja el contenedor -- los datos en Postgres/Vault no se tocan:

```bash
meridianctl cron disable --id <job_id>
docker compose --env-file .env -f docker/docker-compose.yml down
```

Para retomarlo después: `meridianctl vault unseal` (Vault siempre se sella al
reiniciarse) y `meridianctl dev up` (o `docker compose ... --profile mi-profile up -d`
para incluir tu subagente).

---

## Problemas comunes

- **`VAULT_TOKEN not set` al correr `docker compose` a mano** -- usa siempre
  `docker compose --env-file .env -f docker/docker-compose.yml ...`, explícito. Compose no
  siempre resuelve el `.env` de la raíz solo por el `-f` a una subcarpeta.
- **Vault "unhealthy" o comandos de Vault fallan tras reiniciar Docker** -- se sella solo
  al reiniciarse (por diseño de Vault, no un bug). Corre `meridianctl vault unseal`.
- **`Falta SUBAGENT_ID en el entorno`** en los logs del contenedor -- te faltó poner
  `MI_SUBAGENTE_SUBAGENT_ID=<subagent_id>` en tu `.env` antes de levantar el contenedor
  (o el subagente aún no existe -- revisa el paso 5.3).
- **El intent nunca llega al subagente** -- revisa `meridianctl allow list --gateway
  <gateway_id>`: sin una entrada ahí para tu `intent_type`, `main` lo rechaza en
  silencio (queda como `denied` en `meridianctl audit tail`, no como error).
- **El intent se queda "pending" para siempre** -- tu subagente probablemente tiene la
  policy default conservadora (`requires_approval_intents: ["*"]`). Revisa
  `meridianctl approvals list` y aprueba/deniega, o pon una policy explícita como en el
  paso 5.5.
