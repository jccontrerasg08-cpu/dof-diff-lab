# Evaluación de prácticas de pruebas externas

La página compartida, https://qaskills.sh/skills?q=test&page=1, se abrió y verificó directamente en Chrome como un catálogo de más de 500 habilidades de QA. La carga de su contenido dinámico agotó el tiempo de respuesta de la extensión antes de poder confirmar tarjetas individuales, por lo que no se instaló ni se ejecutó ninguna habilidad desde ese sitio.

Como contraste, la búsqueda de habilidades en repositorios verificados devolvió candidatos de pruebas de aplicaciones web, pruebas combinatorias y defensa en profundidad. El resultado se obtuvo desde caché después de que la consulta en línea falló; por tanto, sirve solo como referencia inicial, no como prueba de vigencia.

| Candidato externo | Pertinencia para DOF Diff Lab | Decisión inicial |
|---|---|---|
| Pruebas de aplicaciones web con navegador | El proyecto es un CLI local y no tiene aplicación web. | Descartar: añadir navegador o Playwright no cubre un riesgo actual. |
| Pruebas combinatorias por pares | Las combinaciones de opciones de CLI crecen, pero el contrato actual tiene pocas variables. | No instalar: primero añadir casos explícitos a la comprobación existente. |
| Defensa en profundidad | Coincide con la validación de rutas y URLs ya implementada. | Reutilizar el principio, no una dependencia: probar que un error no crea ni altera archivos. |

La recomendación mínima es añadir una prueba de **atomicidad de salida**: si fallara la escritura del manifiesto, el CLI no debería dejar un informe HTML sin su evidencia solicitada. Esta recomendación surge del flujo actual y no requiere adoptar código o una habilidad externa.

## Contraste con búsqueda web y repositorio de QA verificado en Chrome

La búsqueda solicitada en Google no pudo completar su carga en Chrome por un agotamiento de tiempo de la extensión. Como alternativa, se recuperaron resultados de un índice web y se verificó directamente en Chrome el repositorio `petrkindlmann/qa-skills`. El repositorio declara 50 habilidades de QA que incluyen pruebas unitarias, estrategia de pruebas, CI/CD, pruebas de navegador, API, rendimiento, accesibilidad y seguridad.[1]

| Habilidad o categoría revisada | Encaje con DOF Diff Lab | Decisión |
|---|---|---|
| `unit-testing` | Aporta patrones para el mismo nivel de pruebas ya usado, pero el proyecto mantiene una única comprobación estándar sin framework. | Mantener el enfoque actual; no instalar skill ni framework. |
| `test-strategy` y pruebas basadas en riesgo | Ayudan a razonar qué fallos justifican pruebas. | Aplicar el principio de forma manual: priorizar sobrescritura, evidencia y entradas largas. |
| `test-reliability` y curación de suite | Útil si la comprobación crece o se vuelve inestable. | Posponer: una prueba autocontenida y determinista no lo necesita todavía. |
| Playwright, Cypress, visual, API, móvil, rendimiento, CI/CD | El proyecto no tiene UI, API, servicio ni pipeline configurado. | Descartar por alcance actual. |

[1]: https://github.com/petrkindlmann/qa-skills "petrkindlmann/qa-skills — QA Skills for AI Agents"

La lectura del archivo `unit-testing/SKILL.md` confirmó principios que ya encajan con el proyecto: pruebas de comportamiento mediante la interfaz pública, ejecución rápida y determinista, y cobertura de errores relevantes. También propone `pytest`, umbrales de cobertura, mutación y CI, pero esas herramientas exceden el tamaño y dependencia actual de una única comprobación estándar. La recomendación se mantiene: tomar los principios, no importar el framework ni crear configuración de cobertura todavía.[2]

[2]: https://github.com/petrkindlmann/qa-skills/tree/main/skills/unit-testing "qa-skills — unit-testing"

## Selección para DOF Diff Lab

| Prioridad | Práctica o habilidad | Uso recomendado | Estado |
|---|---|---|---|
| 1 | Principios de pruebas unitarias | Mantener casos públicos, deterministas y centrados en fallos observables de CLI. | Ya aplicado. |
| 2 | Pruebas basadas en riesgo | Antes de cada incremento, cubrir primero pérdida de evidencia, sobrescritura, entradas inválidas y regresiones con líneas extensas. | Ya aplicado manualmente. |
| 3 | Curación de suite | Separar casos solo si `tests/check_cli.py` deja de ser legible o tarda demasiado. | Pospuesto con criterio claro. |
| 4 | Cobertura o mutación | Añadir solo al aparecer lógica de transformación más compleja o varios módulos. | No adoptar ahora. |
| 5 | Navegador, API, CI, rendimiento y pruebas visuales | Requerirían una superficie web, servicio, pipeline o volumen que no existe. | Excluido por YAGNI. |

El siguiente paso no requiere otra habilidad: mantener la comprobación estándar y añadir un caso de regresión cuando se descubra un fallo real. Esa estrategia produce una suite pequeña que prueba el comportamiento de extremo a extremo sin mocks ni dependencias adicionales.

## Auditoría de fiabilidad posterior

La auditoría local confirmó que el repositorio no tiene configuración de dependencias, empaquetado ni automatización de integración continua; el flujo se apoya en Python estándar y `pdftotext`. La comprobación ya cubre entradas inválidas, URL, sobrescritura de fuentes, manifiestos y líneas extensas. Persisten dos riesgos concretos que justifican un incremento pequeño.

| Riesgo | Impacto | Control mínimo propuesto |
|---|---|---|
| Un nombre de informe o manifiesto ya existente se sobrescribe silenciosamente. | Pérdida de evidencia generada con otra ejecución. | Rechazar destinos existentes de forma explícita. |
| La suite se ejecuta solo de forma manual. | Una modificación futura puede publicarse sin la comprobación disponible. | Ejecutar `tests/check_cli.py` en GitHub Actions con Python 3.12 y `poppler-utils`. |

No se añadirá un framework, cobertura, gestor de dependencias, OCR, red ni API. El proyecto no tiene complejidad suficiente para justificar esos cambios.
