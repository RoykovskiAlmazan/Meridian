# Compatibilidad con MySQL/MSSQL (además de Postgres)

Estado: Postgres y MySQL verificados end-to-end. MSSQL soportado por el mismo código,
sin probar en este entorno (ver sección 4).

## 1. Por qué esto fue un rediseño, no un parche

`identity/repository.py` usaba SQL crudo específico de Postgres: tipo `UUID` nativo,
`gen_random_uuid()`, `JSONB`, arrays `TEXT[]`, `ON CONFLICT ... DO UPDATE`. Nada de eso
existe igual en MySQL o MSSQL. La única forma honesta de dar soporte real (no solo "en
teoría") era migrar a una capa de abstracción -- se eligió **SQLAlchemy Core** (no el ORM
completo: se querían las mismas funciones planas de `repository.py` de siempre, solo con
las queries construidas de forma portable, no un cambio de paradigma a objetos mapeados).

## 2. Qué cambió

- **`meridian/identity/schema_meta.py`** (nuevo) -- las 10 tablas definidas una sola vez
  con `sqlalchemy.Table`, usando `.with_variant(...)` para que **Postgres siga usando sus
  tipos nativos** (UUID, JSONB, ARRAY) -- exactamente lo que ya tenían las tablas creadas
  por el schema SQL viejo -- mientras que MySQL/MSSQL usan equivalentes portables
  (`CHAR(36)`, `JSON`). Esto es clave: **no hizo falta ninguna migración de datos** en la
  instalación de Postgres real de Rodrigo, se verificó leyendo y escribiendo sobre las
  tablas ya existentes sin tocarlas.
- **`meridian/config.py`**: nueva variable `DB_BACKEND` (`postgres` default | `mysql` |
  `mssql`) + `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` genéricas (con fallback
  a las `POSTGRES_*` de siempre si no están definidas, para no romper instalaciones
  existentes). `settings.database_url` arma la URL de SQLAlchemy según el backend.
- **`meridian/identity/db.py`**: ahora expone `get_engine()`/`get_conn()` sobre SQLAlchemy
  en vez de `psycopg` directo.
- **`meridian/identity/repository.py`**: reescrito completo con `sqlalchemy.select/insert/
  update/delete` contra las tablas de `schema_meta.py`. Los ids se generan en Python
  (`uuid.uuid4()`) al insertar, no como default de la base -- necesario porque no todos los
  motores generan UUIDs igual de bien vía servidor.
- **`meridian/schema_apply.py`**: ahora es `metadata.create_all(engine)` -- portable e
  idempotente por diseño de SQLAlchemy.
- **`meridianctl doctor`**: `_check_database` genérico (antes `_check_postgres`), usa
  `sqlalchemy.inspect()` en vez de una query a `information_schema` específica de Postgres.

## 3. Verificación hecha

- **Postgres** (la instalación real, con datos reales de toda la sesión): lectura de
  tenants/gateways existentes sin tocarlos, luego CRUD completo (tenant → gateway →
  subagente → allowlist → audit_log) contra la base real, y el flujo end-to-end completo
  (fan-out a 2 subagentes vía Docker) reconstruyendo todos los contenedores con el
  `repository.py` nuevo -- sin ninguna diferencia de comportamiento.
- **MySQL 8** (contenedor real, aislado, nunca antes usado): `apply_schema()` creó las 10
  tablas; CRUD completo (tenant, gateway, subagente, allowlist con lista JSON, policy con
  dict JSON, audit_log) verificado leyendo los valores de vuelta con los tipos Python
  correctos (`list`, `dict`); `meridianctl doctor` reconoció correctamente
  `DB_BACKEND=mysql` y confirmó el schema completo.

## 4. MSSQL: soportado por diseño, no probado

El mismo código (`schema_meta.py`, `repository.py`, `config.database_url` con dialecto
`mssql+pyodbc`) debería funcionar contra SQL Server sin cambios adicionales -- MSSQL no
tiene peculiaridades que este código no maneje ya (usa `CHAR(36)`/`JSON` igual que MySQL).
No se verificó end-to-end en esta sesión porque:

- Requiere el **driver ODBC de Microsoft** instalado a nivel de sistema operativo (no es
  instalable solo con `pip`) -- se agregó como extra opcional
  (`pip install -e ".[mssql]"`, que trae `pyodbc`) pero el driver del SO no está disponible
  en este entorno.
- La imagen oficial de SQL Server (`mcr.microsoft.com/mssql/server`) tiene requisitos de
  licencia/arquitectura (no corre en todas las plataformas igual que Postgres/MySQL) que
  no se validaron aquí.

**Recomendación**: si Rodrigo necesita MSSQL en concreto, el siguiente paso es levantar un
contenedor de SQL Server real (o una instancia de prueba en Azure) e instalar el driver
ODBC, y correr la misma prueba que se hizo con MySQL (`apply_schema()` + CRUD completo) --
la expectativa es que funcione directo, pero "debería funcionar" no es lo mismo que
"se probó", y no se quiere afirmar lo segundo sin haberlo hecho.

## 5. Cómo usar un backend distinto

```bash
# En tu .env
DB_BACKEND=mysql
DB_HOST=localhost
DB_PORT=3307
DB_NAME=meridian
DB_USER=meridian
DB_PASSWORD=meridian_dev_only

# Levantar MySQL (perfil opcional del compose)
docker compose -f docker/docker-compose.yml --profile mysql-db up -d mysql

# Crear el schema y confirmar
meridianctl doctor --fix
```

## 6. Qué NO se migró de paso (fuera de alcance)

- `docker/init/postgres_schema.sql` (el script SQL crudo original) se mantiene como está,
  solo para el arranque automático de un volumen nuevo de Postgres vía
  `docker-entrypoint-initdb.d` -- ya no es la fuente de verdad del schema (lo es
  `schema_meta.py`), pero seguir soportándolo evita romper el flujo de instalación de
  Postgres de siempre. `meridianctl doctor --fix` (que sí usa `schema_meta.py`) cubre lo
  mismo si se prefiere no depender del script SQL.
- Una migración de columnas real (Alembic) sigue sin existir -- `create_all()` solo crea
  tablas que faltan por completo, no agrega columnas a una tabla ya creada con un schema
  viejo. Ya anotado como mejora pendiente en
  [0012-improvement-opportunities.md](docs/design/0012-improvement-opportunities.md).
