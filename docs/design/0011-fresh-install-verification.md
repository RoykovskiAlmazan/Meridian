# Verificación de instalación en limpio ("virgen")

Estado: verificado end-to-end el 2026-09-10, en un stack de Docker completamente aislado
del entorno de desarrollo real (proyecto Compose, red, volumen y puertos distintos).

## 1. Qué se probó y cómo

Se levantó una segunda instalación de Meridian en la misma máquina, totalmente separada
de la que se usó durante todo el desarrollo:

- Proyecto Docker Compose distinto (`-p meridian_freshtest`) — contenedores, red y volumen
  con nombres propios, sin tocar los del entorno real.
- Volumen de Postgres nuevo (creado y **borrado** al final) — el schema se generó 100%
  desde `docker-entrypoint-initdb.d` ejecutando `docker/init/postgres_schema.sql` de cero,
  no con ningún `docker exec psql` manual como se había hecho durante el desarrollo.
- Vault en modo dev nuevo (sin ningún secreto pre-cargado).
- Puertos de host distintos (Postgres 5433, Redis 6380, Vault 8201, mock_gateway 8081) vía
  las variables `POSTGRES_HOST_PORT`/`REDIS_HOST_PORT`/`VAULT_HOST_PORT` nuevas (ver
  sección 3) — el entorno real siguió corriendo en sus puertos de siempre sin interrupción.
- Subred Docker distinta (`172.29.1.0/24` en vez de `172.28.1.0/24`) vía un archivo de
  override temporal, para que ambas redes `internal` pudieran coexistir.

Sobre esa instalación limpia se corrió:

1. `meridianctl doctor` → todos los chequeos en `[OK]`, incluyendo el schema completo
   generado desde cero.
2. Alta de tenant, gateway (con secreto real resuelto ida y vuelta contra el Vault nuevo),
   subagente y allowlist.
3. Un subagente de prueba (`sample_subagent_a`) levantado en el stack aislado.
4. Un `TaskIntent` disparado vía el `mock_gateway` del stack aislado (puerto 8081) →
   `main` (del stack aislado) autorizó, ruteó, el subagente respondió, fan-in agregado —
   el mismo flujo del entregable 2, ahora probado en una instalación que nunca vio los
   datos ni la configuración de desarrollo.

## 2. Resultado

**Correcto de punta a punta.** El único tropiezo fue mío, no del producto: en un paso
intermedio corrí `meridianctl tenant create` sin las variables de entorno de la instalación
aislada activas en esa misma invocación de shell (el estado de shell -- variables
exportadas -- no persiste entre comandos de la herramienta que uso), así que ese comando
puntual escribió por error un tenant de prueba (`freshtest-org`) en la base de datos real.
Se detectó de inmediato (`tenant list` mostró un tenant que no debía estar ahí) y se borró
con `DELETE FROM tenants WHERE name = 'freshtest-org'` antes de continuar. No afectó
ninguna tabla relacionada (no llegó a tener gateways/subagentes asociados). Se confirmó al
final que el entorno real quedó exactamente como estaba (`doctor` en verde, `tenant list`
solo con `mercadazo`).

## 3. Mejora real que salió de esta prueba: puertos de host parametrizables

Antes de esta verificación, `docker/docker-compose.yml` tenía los puertos de host
hardcodeados (`"5432:5432"`, etc.), lo que hace imposible correr dos instalaciones de
Meridian en la misma máquina. Se cambió a:

```yaml
ports:
  - "${POSTGRES_HOST_PORT:-5432}:5432"
```

(mismo patrón para Redis, Vault y `mock_gateway`, que ya tenía `MOCK_GATEWAY_PORT`).
Documentado como variables opcionales en `.env.example`. Esto no cambia el comportamiento
por defecto (sigue siendo 5432/6379/8200/8080 si no se define nada) pero ahora es posible
tener una segunda instalación en paralelo, útil tanto para pruebas como para quien quiera
correr un entorno de staging y uno de producción en la misma máquina.

## 4. Otro hallazgo (documentado, no un bug del producto): los prompts ocultos no son
   automatizables por pipe en Windows

Al intentar automatizar la prueba con `echo "token" | meridianctl gateway create ...`, el
comando se quedó colgado esperando input interactivo -- en Windows, `hide_input=True` de
Click/Typer lee del teclado directamente (vía consola), no de `stdin`, así que no se le
puede "alimentar" por pipe. Esto es correcto para el uso normal (evita que un secreto
quede en el historial de shell, que era justamente el bug que se corrigió en el entregable
7), pero es una limitación real para automatizar altas de gateways en scripts/CI. Ver la
sección de mejoras propuestas para una salida (variable de entorno opcional como
alternativa explícita al prompt, nunca como default).

## 5. Limpieza

Se bajó el stack aislado (`down -v`, incluyendo su volumen) y se borraron las imágenes
Docker y los archivos temporales (`.env.freshtest`,
`docker-compose.freshtest.override.yml`) usados solo para esta prueba -- no quedó rastro
en el repo ni en el entorno real.
