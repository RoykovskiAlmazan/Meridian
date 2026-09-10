# Notas de despliegue en producción / nube (AWS, GCP, Azure)

Estado: documentación de mapeo, no una implementación de infraestructura (Terraform/
CloudFormation/etc.) -- nadie pidió eso todavía, y escribir IaC sin un objetivo concreto de
despliegue sería diseñar para un futuro hipotético. Esto es la guía de qué pieza de
Meridian mapea a qué servicio administrado, para cuando haga falta.

## Qué ya es portable hoy

| Pieza de Meridian | Local (Docker Compose) | AWS | GCP | Azure |
|---|---|---|---|---|
| Base de datos | Postgres/MySQL en contenedor | RDS (Postgres o MySQL) | Cloud SQL (Postgres o MySQL) | Azure Database for PostgreSQL/MySQL |
| Secretos | Vault (`file` storage) | Secrets Manager (`aws-sm:`) | Secret Manager (`gcp-sm:`) | Key Vault (`azure-kv:`) |
| Bus de mensajes | Redis (contenedor) | ElastiCache for Redis | Memorystore for Redis | Azure Cache for Redis |
| `main`/gateways/subagentes | Contenedores Docker Compose | ECS Fargate / EKS | Cloud Run / GKE | Container Apps / AKS |

Las primeras dos filas ya tienen el código que las soporta ([0017](docs/design/0017-database-compatibility.md)
para la base de datos, [0019](docs/design/0019-cloud-secret-backends.md) para secretos) --
solo es cuestión de configuración (`DB_BACKEND`, `DB_HOST`, `credential_ref` con el prefijo
correcto). Las últimas dos filas (Redis administrado, orquestación de contenedores) no
requieren ningún cambio de código de Meridian -- Redis administrado habla el mismo
protocolo, y los contenedores ya están hechos (`docker/*.Dockerfile`); solo cambia dónde y
cómo se orquestan.

## Qué SÍ cambiaría de verdad para un despliegue real

1. **Vault en modo producción real**: el backend `file` de [0016](docs/design/0016-vault-persistence.md)
   con Shamir 1-de-1 es apropiado solo para desarrollo local de un operador. Producción
   real quiere:
   - Auto-unseal vía KMS (AWS KMS / GCP Cloud KMS / Azure Key Vault -- sí, Vault puede usar
     Key Vault de Azure para autodesellarse a sí mismo, es un mecanismo distinto de usarlo
     como backend de `SecretRef`) en vez de una clave Shamir en un archivo local.
   - TLS entre servicios (`tls_disable = "false"` + certificados reales).
   - Un backend de almacenamiment distribuido (Raft integrado de Vault, o Consul) en vez
     de `file`, para alta disponibilidad.
   - O bien: saltarse Vault por completo y usar directo el secretos-manager de la nube
     (`aws-sm:`/`gcp-sm:`/`azure-kv:`) para todo, ya que Meridian ya sabe leerlos --
     simplifica la operación a costa de perder la capa de abstracción única de Vault.

2. **Red**: el sandbox de egress por contenedor ([0004](docs/design/0004-sandbox-exec-model.md))
   usa un proxy Squid + una red Docker `internal`. En Kubernetes/ECS, el equivalente son
   políticas de red (`NetworkPolicy` en K8s, security groups/NSGs en ECS/ACI) -- el
   concepto (allowlist de dominios por subagente, deny-by-default) se mantiene, pero el
   mecanismo de aplicarlo cambia por completo según la plataforma de orquestación elegida.

3. **Observabilidad**: los logs JSON a stdout ([0008](docs/design/0008-observability.md))
   ya son compatibles con cualquier recolector de nube (CloudWatch Logs, Cloud Logging,
   Azure Monitor todos ingieren stdout de contenedores tal cual) -- no requieren cambios,
   solo apuntar el recolector de la nube elegida al stdout de los contenedores.

## Por qué no se hizo más que esto ahora

No hay un despliegue concreto en curso -- construir Terraform/Helm/lo que sea para las tres
nubes sin un objetivo real sería trabajo especulativo que probablemente no coincida con lo
que se necesite el día que sí haga falta (¿cuál nube? ¿qué tan grande el despliegue? ¿multi-
región?). Esta tabla es la referencia para cuando esa conversación pase de "algún día" a
"vamos a desplegar esto en \_\_\_\_" -- en ese momento, con la nube y el alcance concretos,
tiene sentido escribir la infraestructura real.
