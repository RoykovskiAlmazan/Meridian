# Compatibilidad de tareas programadas tipo crontab

Estado: ya estaba cubierto por el `cron_gateway` del entregable 5 (`croniter`); se agregó
validación explícita al crear un job.

## Qué ya funcionaba

`meridianctl cron create --schedule` acepta:
- Expresiones cron estándar de 5 campos (`*/15 * * * *`, `0 9 * * 1-5`, etc.) -- sintaxis
  crontab clásica, sin diferencias.
- Macros estilo crontab: `@hourly`, `@daily`, `@weekly`, `@monthly`, `@yearly` (`croniter`
  los traduce a la expresión equivalente).

`@reboot` no aplica (Meridian no tiene el concepto de "reinicio del sistema" que crontab
sí tiene) -- no se soporta, y no debería.

## Qué se agregó

`meridianctl cron create` ahora valida el `--schedule` con `croniter.is_valid(...)` **antes**
de guardar el job -- antes, una expresión inválida solo fallaba silenciosamente dentro del
loop de `cron_gateway` (ver `_is_due()`), sin avisar a quien lo configuró hasta mucho
después. Ahora se rechaza de inmediato con un mensaje claro.

## Verificación hecha

```
@hourly   -> válido, próximo disparo calculado correctamente
@daily    -> válido
@weekly   -> válido
@monthly  -> válido
@yearly   -> válido
*/5 * * * * -> válido
"not a cron" -> inválido, rechazado por `meridianctl cron create`
```
