# Compatibilidad con MySQL/MSSQL (además de Postgres)

Estado: **Postgres, MySQL y MSSQL verificados end-to-end**, los tres contra motores reales
(ver sección 3/4).

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
- **SQL Server 2022** (`mcr.microsoft.com/mssql/server:2022-latest`, contenedor real,
  aislado): se encontró que esta máquina ya tenía instalado el driver ODBC 17 de
  Microsoft (`Get-OdbcDriver` en PowerShell), así que se pudo probar de verdad en vez de
  quedarse en "debería funcionar". Se creó la base `meridian` a mano (SQL Server no la
  crea sola desde la cadena de conexión, a diferencia de Postgres/MySQL), se aplicó el
  schema con `apply_schema()`, y se corrió el mismo CRUD completo que con MySQL --
  incluyendo `allowed_intents`/`policy` guardados y leídos correctamente como `list`/`dict`
  de Python pese a que MSSQL no tiene un tipo `JSON` nativo real (SQLAlchemy lo mapea a
  `NVARCHAR(MAX)` + serialización) -- y `meridianctl doctor` reconociendo
  `DB_BACKEND=mssql`.

## 4. Detalles de MSSQL que sí importaron en la práctica

- El nombre exacto del driver ODBC varía entre máquinas ("ODBC Driver 17..." vs.
  "...18..."). Se agregó `MSSQL_ODBC_DRIVER` (default: `"ODBC Driver 17 for SQL Server"`,
  el que resultó estar instalado aquí) en vez de hardcodear una versión.
- A diferencia de Postgres/MySQL, conectarse con `DB_NAME=meridian` antes de que esa base
  exista falla -- SQL Server no la crea implícitamente. Hay que crearla una vez a mano
  (`CREATE DATABASE meridian`, conectado a `master`) antes de correr `meridianctl doctor
  --fix` por primera vez contra un servidor MSSQL nuevo. No se automatizó esto en
  `doctor` porque requeriría conectarse dos veces con dos DSN distintos (uno a `master`,
  otro a la base de destino) -- una mejora futura razonable si se usa MSSQL seguido.
- El driver ODBC de Microsoft es la única pieza de este soporte que **no** se instala solo
  con `pip` -- sigue siendo un requisito de sistema operativo, documentado en
  `pyproject.toml` (extra `mssql`).

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
