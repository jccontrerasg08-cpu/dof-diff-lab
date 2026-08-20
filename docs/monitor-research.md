# Investigación de base — Monitor DOF

**Fecha de consulta:** 19 de agosto de 2026.

El portal oficial de Datos Abiertos del Sistema de Diario Oficial (SIDOF) declara servicios para consultar diarios por fecha, año y edición; obtener documentos de una edición; y recuperar notas por fecha, código o diario. También enlaza documentación JSON específica para estos servicios. Esta superficie debe ser la primera fuente de ingestión del monitor, con enlace de respaldo a la nota pública del DOF. No se debe basar el producto en una copia no oficial ni en una inferencia jurídica.

GitHub documenta que las ejecuciones programadas usan cron POSIX y UTC. Las programaciones pueden retrasarse bajo carga, particularmente al inicio de cada hora, y los repositorios públicos pueden desactivar flujos programados tras 60 días sin actividad. Por ello, una primera versión alojada exclusivamente en GitHub debe publicar la última ejecución exitosa, deduplicar por identificador oficial y permitir relanzamiento manual; no debe prometer alertas en tiempo real.

| Hallazgo | Implicación de diseño |
|---|---|
| SIDOF enumera consultas de diario, documento y nota en sus datos abiertos. | Captura determinista desde fuente oficial; persistir el identificador, fecha, edición y URL de origen. |
| El DOF oficial ofrece consulta por fecha, edición y búsqueda. | El monitor puede complementar la fuente con un catálogo versionado y enlaces de verificación, no sustituirla. |
| GitHub Actions ejecuta tareas programadas en UTC y puede retrasarlas. | Programar lejos del minuto cero, registrar `checked_at`, usar concurrencia y conservar un `state.json`. |
| Los schedules se desactivan tras inactividad en repositorios públicos. | Documentar la condición y añadir ejecución manual; un commit o la operación manual reactivan el flujo. |

## Referencias

[1]: https://sidof.segob.gob.mx/datos_abiertos "SIDOF — Datos abiertos"
[2]: https://dof.gob.mx/ "Diario Oficial de la Federación"
[3]: https://docs.github.com/actions/using-workflows/events-that-trigger-workflows "GitHub Docs — Events that trigger workflows"
[4]: https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow "GitHub Docs — Disabling and enabling a workflow"

## Contrato confirmado para el primer adaptador

La página `https://sidof.segob.gob.mx/apiStatus` enumera servicios públicos de diario, notas y documentos; por ejemplo, presenta `/diarios/porFecha/03-11-2016`, `/notas/26-08-2016`, `/notas/nota/5469042` y `/documentos/doc/5422563` como rutas de referencia con respuestas exitosas en el momento consultado. El mismo estado también contiene errores 400, 404 y 500, de modo que no se toma como contrato estable de producción ni como prueba de disponibilidad futura.

La documentación JSON de Datos Abiertos `https://sidof.segob.gob.mx/datos_abiertos/getJSON/57` devolvió un ejemplo estructurado de una edición con `NotasMatutinas`, `NotasVespertinas` y `NotasExtraordinarias`. Los registros observados contienen `codNota`, `titulo`, `codSeccion`, `fecha`, `codDiario`, indicadores de disponibilidad (`existeHtml`, `existeDoc`, `existeImagen`), página y los emisores de primer y segundo nivel. Esta respuesta prueba que el portal anuncia una forma estructurada útil, pero el enlace consultado devuelve una muestra de 2016 y no documenta un parámetro diario actual; por ello no se automatizará como endpoint dinámico inicial.

El índice oficial `https://dof.gob.mx/index_113.php?year=2026&month=08&day=18` respondió con una edición matutina, sección, emisores, títulos y enlaces canónicos `nota_detalle.php?codigo=...&fecha=...`. Ésta es la fuente de arranque del adaptador inicial porque permite extraer metadatos y un identificador de nota desde una página oficial observable. El monitor mantiene la respuesta original, su hash y el enlace a cada nota; no lo presenta como sustituto de la publicación oficial.
