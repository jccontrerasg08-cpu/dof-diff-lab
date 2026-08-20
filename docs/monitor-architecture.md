# Arquitectura del monitor diario del DOF

## Objetivo operativo

El repositorio es un monitor autónomo del Diario Oficial de la Federación. Cada ejecución diaria consulta una edición oficial, calcula un hash de la respuesta sin republicar su HTML, produce un catálogo normalizado y etiquetado, compara el resultado con el estado anterior y publica únicamente derivados minimizados y verificables en GitHub. El monitor es informativo: conserva enlaces, hashes y metadatos de la fuente, pero no determina vigencia, obligaciones ni consecuencias jurídicas.

> **Principio de confianza:** el DOF oficial es la fuente primaria. Los registros normalizados, etiquetas e insights son derivados y deben exponer la regla, evidencia y versión que los produjo.

## Fuente y estrategia de captura

La primera fuente será el índice oficial de la edición matutina bajo la ruta documentada y observable `https://dof.gob.mx/index_113.php?year=AAAA&month=MM&day=DD`. La página presenta fecha, edición, secciones, emisores, títulos, enlaces a las notas y sus códigos. SIDOF se mantiene como fuente complementaria futura: anuncia servicios JSON para diario, documentos y notas, pero el contrato de rutas y parámetros no está suficientemente publicado para convertirlo en una dependencia inicial.

La captura es de sólo lectura y usa un agente identificable, timeout finito y sin autenticación. Un estado HTTP distinto de 200, una respuesta vacía o un esquema no reconocible son `source_error` o `parse_error`; nunca equivalen a «sin novedades».

## Artefactos versionados

| Ruta | Contenido | Propósito |
|---|---|---|
| `data/normalized/YYYY-MM-DD/matutina.json` | Registros canónicos por nota, ordenados de forma determinista. | Catálogo consultable y base del diff. |
| `data/manifests/YYYY-MM-DD/matutina.json` | URL, hora UTC, HTTP, MIME, tamaño, hashes, conteos y versión de esquema/reglas. | Procedencia y diagnóstico. |
| `data/diffs/YYYY-MM-DD.md` | Altas, bajas y cambios de metadatos respecto de la última captura equivalente. | Revisión humana diaria. |
| `data/state/latest.json` | Última ejecución exitosa, hash de catálogo y cursor de publicación. | Idempotencia y observabilidad. |
| `site/index.html` | Índice estático de la última ejecución, métricas y enlaces a evidencia. | Consulta en GitHub Pages. |

El repositorio no conserva ni publica el HTML crudo del índice, PDFs, Word, imágenes ni texto completo de cada nota. El manifiesto registra URL, hash SHA-256, MIME y tamaño de la respuesta para verificar la captura sin redistribuir scripts, formularios, identificadores de seguimiento u otros contenidos ajenos a la función del monitor.

## Registro normalizado

Cada nota tiene una identidad de monitor formada por `source_note_code + publication_date + edition`. Si el código no es extraíble, usa la URL canónica como respaldo. El título se conserva tal como lo expone la fuente y no se usa como identificador único.

```json
{
  "schema_version": "1.0",
  "source": {
    "name": "DOF official index",
    "index_url": "https://dof.gob.mx/index_113.php?year=2026&month=08&day=18",
    "publication_date": "2026-08-18",
    "edition": "matutina"
  },
  "note": {
    "code": "5796510",
    "canonical_url": "https://dof.gob.mx/nota_detalle.php?codigo=5796510&fecha=18/08/2026",
    "title": "Acuerdo del Consejo General del Instituto Nacional Electoral...",
    "section": "ORGANISMOS AUTONOMOS",
    "issuer_primary": "ORGANISMOS AUTONOMOS",
    "issuer_secondary": "INSTITUTO NACIONAL ELECTORAL",
    "page_start": null
  },
  "tags": [],
  "insights": [],
  "record_sha256": "..."
}
```

## Etiquetas explicables

Cada etiqueta contiene `name`, `value`, `evidence`, `rule_id`, `rule_version` y `confidence`. La primera versión usa reglas deterministas sobre el título y metadatos del índice; no incorpora modelos ni conclusiones jurídicas.

| Familia | Etiquetas iniciales | Evidencia | Semántica permitida |
|---|---|---|---|
| Documento | `document_type` (`acuerdo`, `decreto`, `resolucion`, `norma`, `convenio`, `aviso`, `circular`, `sentencia`, `convocatoria`, `otro`) | Prefijo o términos del título. | Clasificación documental. |
| Cambio textual | `possible_modification`, `possible_addition`, `possible_repeal`, `possible_abrogation` | Término exacto localizado en título. | Señal de que el título contiene la acción; no confirma efectos jurídicos. |
| Temporal | `contains_effective_date`, `contains_deadline`, `contains_call_for_bids` | Términos como `entra en vigor`, `vigencia`, `plazo`, `convocatoria`, `licitación`. | Señal de prioridad de lectura. |
| Materia | `fiscal`, `trade`, `labor`, `health`, `environment`, `energy`, `financial`, `public_procurement`, `data_protection`, `other` | Diccionario versionado de términos en título/emisor. | Tema de descubrimiento, no ámbito legal exhaustivo. |
| Fuente | `has_html`, `has_word`, `has_image`, `section`, `issuer` | Metadatos observados en el índice. | Hecho de disponibilidad y contexto editorial. |

Los insights son resúmenes cuantitativos derivados y siempre indican que son computados: conteos por tipo, materia, emisor y señales de cambio. No habrá semáforos de impacto ni recomendaciones legales en esta versión.

## Automatización y publicación

Un workflow de GitHub ejecutará diariamente a las **16:17 UTC**, evitará el minuto cero y admitirá `workflow_dispatch` con fecha opcional para recuperación. Usará `concurrency` sin cancelar una ejecución activa; primero hará la captura y validación, luego generará catálogo/diff/sitio y finalmente hará commit sólo si existen cambios verificables. Todo job tendrá permisos mínimos; el job publicador tendrá exclusivamente `contents: write`.

Cada corrida correcta subirá como artifact el catálogo normalizado, manifiesto, diff, estado y sitio; la ausencia de esos derivados falla la corrida. El estado distingue `changed`, `no_change` y `no_edition`; los errores de fuente o parser fallan explícitamente y no se publican como ausencia de novedades. GitHub Pages se despliega a partir del sitio estático generado, sin base de datos ni servicio externo.

## Criterios de aceptación

| Escenario | Resultado verificable |
|---|---|
| Primera captura de fixture oficial | Se crean normalizado, manifiesto, diff e índice estático con hashes coherentes, sin HTML crudo retenido. |
| Segunda captura idéntica | No agrega notas, el diff indica ausencia de cambios y el estado queda `no_change`. |
| Cambio controlado en fixture | El diff identifica alta, baja o modificación por clave estable y muestra tags con regla/evidencia. |
| Fallo de fuente o parser | No sustituye el estado anterior, emite manifiesto/estado de error y no afirma ausencia de novedades. |
| Workflow diario | Puede ejecutarse manualmente con fecha, no se solapa y sólo publica commits al detectar cambios. |

## Fuentes

[1]: https://dof.gob.mx/index_113.php?year=2026&month=08&day=18 "Índice oficial del DOF — ejemplo de edición"
[2]: https://sidof.segob.gob.mx/datos_abiertos "SIDOF — Datos abiertos"
[3]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule "GitHub Actions — ejecución programada"
[4]: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs "GitHub Actions — concurrencia"
