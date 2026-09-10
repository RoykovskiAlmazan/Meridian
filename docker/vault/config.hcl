# Vault con almacenamiento persistente (backend "file") para desarrollo local -- ver
# docs/design/0016-vault-persistence.md. Reemplaza el modo "dev" (in-memory) que se
# usó hasta el entregable 7: cualquier recreación del contenedor en modo dev borra
# TODOS los secretos guardados (se comprobó en la práctica: un cambio no relacionado
# a docker-compose.yml recreó el contenedor de Vault y se perdió una API key real).
#
# Un solo key share / threshold 1 es apropiado SOLO para desarrollo local de un operador
# -- nunca para producción real (ahí se quiere Shamir con varios shares distribuidos
# entre personas distintas, o KMS auto-unseal). Ver sección "Producción" del documento.

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = "true"
}

disable_mlock = true
ui            = false
