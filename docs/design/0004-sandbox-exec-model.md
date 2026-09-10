# Entregable 3 — Sandbox de ejecución/egress para subagentes

Estado: implementado y verificado en esta máquina (Docker Desktop / Windows).

## 1. Decisión

Rodrigo eligió **restricciones a nivel de contenedor**, sin aprobación humana en el camino
crítico por ahora: cada subagente corre en un contenedor que:

1. **No tiene ruta directa a internet.** Está conectado únicamente a una red Docker
   `internal: true` (`meridian_internal`) — Docker no le da salida NAT hacia afuera.
2. **Solo puede salir a través de un proxy de egress** (`egress_proxy`, Squid) que sí tiene
   salida a internet, y que aplica una **allowlist de dominios por subagente** basada en la
   IP fija de cada contenedor dentro de `meridian_internal`.
3. **Sin dominios declarados = sin salida.** El default de Squid es `http_access deny all`;
   un subagente nuevo no llega a ningún dominio hasta que alguien agregue explícitamente su
   IP + los dominios permitidos en `docker/sandbox/squid.conf`. Esto es exactamente el
   "seguro por defecto" no negociable de la sección 5 del brief.
4. El contenedor además corre **sin privilegios de root**, **sin capabilities de Linux**
   (`cap_drop: ALL`), **sin escalación de privilegios** (`no-new-privileges`), y con
   **filesystem raíz de solo lectura** (con `/tmp` como `tmpfs` para lo que necesite escribir
   en caliente). Esto no depende de que el subagente use o no la red — limita el daño si el
   proceso Python del subagente es comprometido de cualquier otra forma.

## 2. Por qué este enfoque y no otro

- Ya habíamos decidido "contenedor por subagente" (sección 8 del brief) — este entregable
  es endurecer ese contenedor, no introducir un mecanismo nuevo de aislamiento.
- Una VM ligera (firecracker) o `seccomp`/AppArmor a mano hubiera sido más aislamiento pero
  mucho más esfuerzo operativo cross-platform (Windows + Linux, requisito explícito de
  Rodrigo) — Docker + red interna + proxy de egress da la mayoría del beneficio con
  herramientas que ya estaban en el stack.
- Se descartó por ahora la aprobación humana explícita (`meridianctl approvals ...`) para no
  bloquear el camino crítico de un subagente automatizado — puede añadirse después como capa
  extra para acciones especialmente sensibles (ej. "cancelar una orden"), sin romper este
  diseño: sería una verificación adicional antes de que el subagente publique su `TaskResult`,
  no un reemplazo del sandbox de red.

## 3. Qué cambió en el repo

- `docker/docker-compose.yml`:
  - Red `meridian_internal` (`internal: true`, subred fija `172.28.1.0/24`) para
    postgres/redis/vault/main_agent/mock_gateway/subagentes.
  - Red `meridian_egress` (bridge normal, con salida a internet) donde solo vive
    `egress_proxy`.
  - Servicio `egress_proxy` (Squid) conectado a ambas redes — es el único puente entre
    `meridian_internal` e internet.
  - `sample_subagent_a` (IP fija `172.28.1.10`) y `sample_subagent_b` (IP fija
    `172.28.1.11`) reciben `HTTP_PROXY`/`HTTPS_PROXY` apuntando a `egress_proxy:3128`, más
    `cap_drop: ALL`, `security_opt: no-new-privileges`, `read_only: true`, `tmpfs: /tmp`.
- `docker/sandbox/squid.conf` — ACLs por IP fija de subagente + dominios permitidos
  (hoy vacío para ambos subagentes de prueba: no hacen llamadas externas todavía).
  Documentado inline cómo agregar un dominio cuando un subagente real lo necesite.
- `docker/subagents/*.Dockerfile` — se agregó un usuario no-root (`appuser`) y se fija
  `USER appuser` antes del `CMD`.

## 4. Cómo agregar acceso a un dominio real (cuando exista un subagente de dominio)

1. Asignarle una IP fija dentro de `meridian_internal` en `docker-compose.yml`
   (siguiente disponible en `172.28.1.0/24`).
2. En `docker/sandbox/squid.conf`, agregar:
   ```
   acl <nombre_subagente> src <ip fija>/32
   acl <nombre_subagente>_allowed_domains dstdomain .dominio-del-marketplace.com
   http_access allow <nombre_subagente> <nombre_subagente>_allowed_domains
   ```
   **antes** de la línea `http_access deny all` (Squid evalúa reglas en orden).
3. Reiniciar `egress_proxy` (`docker compose restart egress_proxy`).

## 5. Verificación hecha (en esta máquina, con Docker Desktop)

- Los subagentes de prueba siguen consumiendo del bus (Redis) y respondiendo normalmente
  con `meridian_internal` como única red hacia el resto de la plataforma — se repitió el
  test end-to-end del entregable 2 (fan-out a los 2 subagentes + fan-in agregado) y siguió
  funcionando igual tras aplicar el sandbox.
- Se confirmó que una request HTTP desde dentro de `sample_subagent_a` (vía `HTTP_PROXY`,
  que ya apunta a `egress_proxy` por variable de entorno) a un dominio no declarado en la
  allowlist (`example.com`) es **rechazada por Squid con `403 Forbidden`** — el default
  "deny all" del punto 1 funciona.

### Bug encontrado y corregido durante la verificación

La primera versión de este entregable puso **todo** (incluido Postgres/Redis/Vault/
mock_gateway) en una única red `internal: true`. Eso rompió el entregable 2: una red
`internal: true` en Docker bloquea no solo la salida a internet sino **también la
publicación de puertos hacia el host** para cualquier contenedor que solo esté en esa red
-- `mock_gateway:8080`, `postgres:5432`, etc. dejaron de ser alcanzables desde fuera de
Docker. Se corrigió agregando una tercera red, `meridian_hostnet` (bridge normal, sin
salida a internet propia más allá de la que ya tiene cualquier red bridge de Docker), y
uniendo a ella únicamente los servicios que necesitan ser alcanzables desde el host
(Postgres, Redis, Vault, mock_gateway). `main_agent` y los subagentes se quedaron
exclusivamente en `meridian_internal` -- no necesitan ser alcanzados desde el host, así que
no ganan ninguna ruta de salida adicional. Ver el comentario extendido en
`docker/docker-compose.yml`.

## 6. Fuera de alcance de este entregable

- Aprobación humana explícita para acciones sensibles — queda como extensión futura, no
  descartada, solo no incluida ahora (ver sección 2).
- Rotación/gestión de la allowlist de dominios vía `meridianctl` (hoy es edición manual de
  `squid.conf`) — se evalúa agregar un comando `meridianctl sandbox allow-domain` si el
  número de subagentes reales crece lo suficiente para justificarlo.
