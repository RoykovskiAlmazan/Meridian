# Oportunidades de mejora (post-verificación de instalación en limpio)

Estado: sección A implementada y verificada el 2026-09-10; sección B es una lista para
decidir con Rodrigo, nada de esto está hecho todavía.

## A. Implementadas en esta ronda

1. **Puertos de host parametrizables** (`POSTGRES_HOST_PORT`/`REDIS_HOST_PORT`/
   `VAULT_HOST_PORT`, además del ya existente `MOCK_GATEWAY_PORT`) — permite correr dos
   instalaciones de Meridian en la misma máquina sin chocar puertos. Salió directamente de
   la prueba de instalación en limpio (ver [0011](docs/design/0011-fresh-install-verification.md)).
2. **`main_agent`, `mock_gateway` y `cron_gateway` ahora corren sin privilegios de root**
   (usuario `appuser`, `cap_drop: ALL`, `no-new-privileges`, filesystem de solo lectura) —
   antes solo los subagentes tenían este endurecimiento; era una inconsistencia con "seguro
   por defecto" (sección 5 del brief) que estos tres procesos, que también tocan Postgres/
   Redis/Vault, corrieran como root.
3. **`--from-file` en `secrets put` y `gateway create`/`rotate-credential`** — alternativa
   al prompt oculto para scripts/CI. Se descubrió durante la prueba de instalación en
   limpio que el prompt oculto (correcto por seguridad) no se puede alimentar por pipe en
   Windows, lo que hacía imposible automatizar el alta de gateways. `--from-file` lee el
   valor de un archivo local (nunca de un argumento de CLI ni de una variable de entorno,
   ambos más fáciles de exponer por accidente que un archivo).
4. **Healthchecks de Postgres/Redis/Vault** + `depends_on: condition: service_healthy` en
   todos los servicios que dependen de ellos — antes `depends_on` solo esperaba a que el
   contenedor *arrancara*, no a que el servicio adentro estuviera *listo*; en máquinas más
   lentas esto podía causar errores de conexión intermitentes al primer `docker compose up`.

Todo lo anterior se verificó reconstruyendo el stack completo y repitiendo el flujo
end-to-end (fan-out a 2 subagentes, fan-in, `doctor` en verde).

## B. Propuestas, no implementadas (para decidir)

Ordenadas por qué tan directo es el beneficio vs. esfuerzo, no por prioridad fija:

1. **Suite de pruebas automatizadas.** `tests/unit/` y `tests/integration/` siguen vacías
   (solo `.gitkeep`). Para una beta que otros van a tocar, al menos pruebas unitarias de
   `messages.py` (validación de schema), `main_agent/core.py` (`authorize_and_route` con
   casos allow/deny) y `policy.py` darían una red de seguridad real contra regresiones.
2. **CI en GitHub Actions.** Un workflow que corra `py_compile`/pytest (una vez exista la
   suite del punto 1) en cada push/PR — hoy toda la verificación fue manual, en esta
   máquina, por mí.
3. **`meridianctl init` interactivo.** Un wizard que encadene `doctor --fix` → `dev up` →
   alta de un primer tenant/gateway/subagente, para bajar la fricción de los primeros 5
   minutos de alguien nuevo. El quickstart del README ya cubre esto paso a paso, pero un
   wizard es más amigable.
4. **Persistencia del estado de fan-in del `main`.** Documentado desde el entregable 2
   como limitación conocida: si el `main` se reinicia a mitad de un fan-out, esa agregación
   puntual se pierde (los subagentes sí procesan, pero nadie los agrega). Movible a Redis
   (ej. un hash por `correlation_id` con TTL) sin cambiar el contrato de mensajes.
5. **Reintentos/dead-letter en el bus.** Ni `main` ni los subagentes reintentan ni mueven a
   una cola de "muertos" un mensaje que falla repetidamente (`XPENDING`/`XCLAIM` de Redis
   Streams no están implementados). Hoy un fallo transitorio de un subagente no se
   recupera solo.
6. **Adapter de Gemini.** El schema de `subagent_llm_config` y la CHECK constraint ya
   aceptan `'gemini'` como proveedor válido, pero `meridian/llm/registry.py` no tiene el
   adapter -- es el mismo patrón que Anthropic/OpenAI, solo falta escribirlo (y probarlo,
   lo cual requiere una API key de Google que hoy no está disponible).
7. **Enforcement real de `subagent_policy`.** Sigue siendo solo datos (ver
   [0005](docs/design/0005-behavior-policy.md) sección 4) — ni el `main` ni los subagentes
   consultan `requires_approval_intents`/`destructive` antes de actuar todavía.
8. **Linting/type-checking** (`ruff`, `mypy`) — no hay ninguno configurado hoy; ayudaría a
   sostener la calidad del código a medida que crezca más allá de lo que yo escribí en esta
   sesión.
9. **Ancho de tablas de Rich en terminales angostas/no interactivas.** Cosmético, no
   funcional -- en una terminal real e interactiva se ve bien, pero columnas como `id`
   (UUIDs completos) se truncan feo en salidas muy angostas o cuando se redirige a un
   archivo/pipe.
10. **Documentar un despliegue de producción real.** Todo lo construido asume Vault en modo
    dev (in-memory, se pierde al reiniciar) y Postgres/Redis sin TLS ni backups -- son
    decisiones correctas para desarrollo local, pero el repo no dice todavía qué cambiar
    para un despliegue real (Vault en modo producción con unseal keys, TLS entre
    servicios, backups de Postgres, etc.).

Ninguna de estas se implementó sin pedirlo -- son candidatas, no compromisos.
