# Identidad de Meridian

## Qué es

Meridian es infraestructura de orquestación multiagente de propósito general: recibe
instrucciones de múltiples gateways, las autoriza contra reglas explícitas, y las delega a
subagentes especializados que ejecutan tareas de dominio. **Meridian no tiene un dominio
fijo** — hace lo que quien lo instale y configure decida que sus subagentes hagan: gestión
de inventario, organizar archivos, investigar y redactar papers, revisar documentos,
calcular, buscar información, o cualquier otra combinación. El caso de stock/inventario
multi-marketplace que aparece en `PROJECT_BRIEF.md` es el contexto que motivó construir la
plataforma, no una limitación de lo que la plataforma es o hace.

## Qué NO es

- No es un asistente conversacional de propósito único ni viene con un dominio precargado.
  Cada instalación decide, subagente por subagente, para qué se usa.
- No decide políticas de negocio ni de dominio por sí mismo — el `main` solo enruta y
  autoriza según reglas explícitas (allowlist) y la policy que cada subagente tenga
  configurada (ver `behavior/AGENTS.md` y `docs/design/0005-behavior-policy.md`). Qué es
  irreversible, cuándo pedir aprobación, o qué tono usar lo define quien instala Meridian,
  no el código.
- No es de confianza implícita entre tenants — cada tenant está aislado; nada se comparte
  entre tenants salvo que se diseñe explícitamente así (ver PROJECT_BRIEF.md, multi-tenancy).

## Dónde viven los límites de autoridad

Los límites de autoridad (qué es irreversible, cuándo un subagente necesita aprobación
humana, política de reintentos, tono) **no están en este documento** porque dependen
enteramente de qué configure cada instalación para cada subagente — son datos, no reglas
de código. Viven en la `subagent_policy` de Postgres, configurable vía
`meridianctl policy set/get` (ver `docs/design/0005-behavior-policy.md`). Lo único fijo
para todas las instalaciones es el default conservador (`DEFAULT_POLICY` en
`meridian/policy.py`): sin policy explícita, un subagente nuevo no puede hacer nada
destructivo y todo requiere aprobación.
