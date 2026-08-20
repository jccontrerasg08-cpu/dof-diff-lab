# DOF Monitor Lab

**DOF Monitor Lab** es un monitor diario, informativo y trazable del Diario Oficial de la Federación (DOF). Consulta el índice oficial, genera un catálogo mínimo de metadatos y publica etiquetas deterministas para facilitar el descubrimiento y la revisión.

> **No afiliación y uso responsable.** Este proyecto no está afiliado, patrocinado ni respaldado por el DOF ni por una autoridad pública. La **fuente primaria** es siempre la publicación oficial enlazada. Los catálogos, etiquetas, hashes y resúmenes de este repositorio son derivados técnicos: no certifican autenticidad jurídica, no determinan vigencia ni efectos regulatorios, y **no sustituyen** la consulta del DOF ni asesoría jurídica o profesional.

## Qué publica el monitor

El proyecto aplica minimización de datos. No republica HTML, formularios, scripts, identificadores de analítica, PDFs, imágenes o texto íntegro obtenidos del sitio fuente. Para cada captura conserva la URL oficial, el hash SHA-256, el tamaño y un catálogo normalizado de los metadatos estrictamente necesarios para trazabilidad.

| Artefacto | Contenido | Finalidad |
|---|---|---|
| `data/normalized/YYYY-MM-DD/matutina.json` | Código, URL oficial, título, sección, emisor, etiquetas y hash por nota. | Búsqueda, análisis y comparación reproducible. |
| `data/manifests/YYYY-MM-DD/matutina.json` | Procedencia: URL, HTTP, MIME, tamaño, hash y estado de la captura. | Distinguir fuente observada de datos derivados. |
| `data/diffs/YYYY-MM-DD.md` | Altas, bajas y modificaciones del catálogo normalizado. | Revisión diaria legible. |
| `data/state/latest.json` | Estado e identidad de la última ejecución. | Supervisión operacional. |
| `site/index.html` | Resumen con etiquetas, regla, evidencia textual y enlace oficial de cada nota. | Consulta pública explicable. |

## Etiquetas e insights explicables

Las etiquetas se derivan exclusivamente de reglas deterministas aplicadas al título y metadatos visibles del índice. La interfaz pública muestra, junto a cada nota, el identificador y versión de la regla, el fragmento activador y el enlace a la fuente oficial. Una etiqueta expresa una **coincidencia de regla**, no una probabilidad, dictamen ni conclusión jurídica.

| Grupo | Ejemplos | Límite de interpretación |
|---|---|---|
| Tipo documental | `acuerdo`, `decreto`, `resolucion`, `norma` | Clasificación derivada de términos explícitos del título. |
| Señales textuales | `possible_modification`, `possible_repeal`, `contains_deadline` | Invitan a leer la publicación; no confirman efectos jurídicos. |
| Materias de descubrimiento | `fiscal`, `trade`, `labor`, `health`, `environment` | Facilitan filtros; no son una cobertura jurídica exhaustiva. |

## Ejecución manual

```text
python3 -m dof_diff_lab.monitor --date 2026-08-18 --root .
```

La fecha se interpreta como fecha de publicación del índice oficial y las marcas de tiempo se guardan en UTC. Una respuesta inesperada, un error de red o un error de parseo termina con código distinto de cero; nunca equivale a «sin novedades».

## Automatización diaria en GitHub

El workflow se ejecuta diariamente a las **16:17 UTC** y admite ejecución manual con fecha ISO opcional. GitHub puede retrasar tareas programadas, por lo que el manifiesto conserva la hora real de captura y la operación puede repetirse manualmente.[1]

El flujo usa la publicación oficial como fuente primaria, valida la fecha manual, conserva sólo derivados minimizados y actualiza el repositorio únicamente tras una ejecución correcta. El sitio incluye `noindex` y no enlaza a contenido crudo del sitio fuente.

## Desarrollo y comprobaciones

```text
python3 tests/check_monitor.py
python3 tests/check_monitor_workflow.py
python3 tests/check_public_readiness.py
python3 tests/check_cli.py
```

Estas son las verificaciones canónicas antes de proponer un cambio. Consulte [`docs/monitor-architecture.md`](docs/monitor-architecture.md) para el contrato de datos, [`SECURITY.md`](SECURITY.md) para reportes responsables y [`LICENSE`](LICENSE) para permisos sobre el código.

## Licencia y atribución

El código propio se publica bajo la licencia Apache-2.0. Los contenidos del DOF continúan sujetos a sus condiciones y a la publicación oficial; este repositorio no pretende relicenciarlos ni sustituirlos. Al citar un resultado, incluya la URL oficial, fecha de publicación, hash del manifiesto y commit del repositorio.

## Referencias

[1]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule "GitHub Actions — programación de workflows"
[2]: https://dof.gob.mx/index_113.php?year=2026&month=08&day=18 "DOF — ejemplo de índice oficial"
