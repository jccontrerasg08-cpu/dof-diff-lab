# Mapa de componentes abiertos para DOF Diff Lab

La búsqueda se limita a problemas que el flujo actual no resuelve y que son suficientemente comunes como para preferir una herramienta madura antes que código propio.

| Área del flujo | Estado actual | Necesidad real | Tipo de componente a investigar |
|---|---|---|---|
| PDFs escaneados | Se rechazan cuando `pdftotext` no produce texto. | Crear una capa textual local conservando el original. | OCR de PDF local. |
| Diferencias de maquetación | El HTML muestra diferencias textuales; no permite revisar desplazamientos visuales de tablas. | Comparación visual solo como evidencia complementaria. | Diferenciador visual de PDF. |
| Tablas arancelarias | El diff por línea falla cuando el origen mezcla columnas o celdas. | Extracción tabular solo si una muestra real bloquea la revisión. | Extractor de tablas para PDF digital u OCR estructurado. |
| PDFs dañados o cifrados | `pdftotext` devuelve un error, sin diagnóstico específico. | Diagnóstico antes de extracción cuando el fallo sea frecuente. | Preflight y reparación de PDF. |
| Fuentes y archivos | El manifiesto guarda hashes y URLs proporcionadas. | Ninguna: el flujo no debe descargar ni vigilar páginas. | No buscar integraciones de red. |
| CLI y pruebas | La suite autocontenida y CI cubren el comportamiento actual. | Ninguna: no añadir framework o dashboard. | No buscar herramientas de pruebas adicionales. |

La prioridad es investigar OCR, comparación visual, extracción tabular y preflight. Ninguna herramienta se adoptará sin que resuelva un fallo observado o una muestra real que el flujo no pueda revisar.

## Candidatos verificados en Chrome

| Proyecto | Hallazgo verificado | Decisión preliminar |
|---|---|---|
| [QPDF](https://github.com/qpdf/qpdf) | Herramienta de línea de comandos para transformaciones que preservan contenido e inspección estructural; no renderiza ni extrae texto. | Posponer: es un buen preflight si aparecen PDFs corruptos o cifrados con frecuencia, pero no mejora la comparación normal. |
| [Camelot](https://github.com/atlanhq/camelot) | Extrae tablas de PDFs basados en texto, pero declara explícitamente que no funciona con documentos escaneados. | No integrar: no resuelve el caso OCR y añade dependencias; podría reevaluarse solo para un modo tabular de PDFs digitales. |

La verificación confirma que la ruta OCR estructurada (PaddleOCR) sigue siendo el único escalón razonable para tablas escaneadas, mientras que QPDF es diagnóstico opcional y Camelot queda fuera del alcance actual.

| [diff-pdf](https://github.com/vslavik/diff-pdf) | Verificado en Chrome: genera un PDF con diferencias visuales y ofrece una vista gráfica; el propio repositorio declara que no está en desarrollo activo. | No integrar al CLI ni al CI. Puede servir como herramienta manual y opcional si una revisión humana necesita inspeccionar cambios de diseño que el diff textual no explica. |

## Priorización de integración

| Prioridad | Componente | Aporta a qué parte | Integración mínima o condición | Decisión |
|---:|---|---|---|---|
| 1 | OCRmyPDF + Tesseract `spa` | Permite comparar PDFs escaneados dentro del mismo flujo de hash, manifiesto y HTML. | Añadir un modo OCR local que produzca un PDF derivado y marque la fuente como OCR. | Integrar después de probar con una muestra escaneada real. |
| 2 | PaddleOCR / PP-Structure | Puede aportar lectura de celdas cuando OCR simple no respete la estructura de tablas. | Crear un modo separado con salida estructurada; nunca reemplazar silenciosamente el diff textual. | Posponer hasta medir errores de tabla reales. |
| 3 | QPDF | Diagnostica problemas estructurales antes de que `pdftotext` u OCR fallen sin explicación. | Ejecutar `qpdf --check` solo después de que haya una recurrencia de PDFs inválidos o cifrados. | No instalar hoy. |
| 4 | diff-pdf | Ayuda a una persona a ver desplazamientos visuales, sellos o cambios de maquetación. | Uso manual de escritorio y PDF de evidencia separado. | No integrar ni automatizar. |
| — | Camelot | Extrae tablas digitales, no escaneos. | Requeriría un modo tabular específico y dependencias Python. | Descartar por ahora. |

La mejor ganancia fuera de OCR no es otra dependencia: es conservar la separación actual entre evidencia binaria (hash), contenido leído (texto/OCR) y contexto de origen (URL). Los otros componentes solo deben entrar cuando una muestra concreta demuestre que esta evidencia no basta para revisar el cambio.

## Repositorio marcado relevante: pdf-inspector

La verificación en Chrome confirmó que `firecrawl/pdf-inspector` clasifica PDFs como texto, escaneados, imagen o mixtos, y extrae Markdown con lectura multicolumna y detección de tablas **sin OCR**. Su utilidad para DOF Diff Lab no es reconocer escaneos, sino decidir localmente cuándo evitar OCR y producir una extracción más estructurada para PDFs digitales. El proyecto declara una dependencia Rust ligera, pero sus vías de integración requieren CLI de Cargo, Node o compilación de bindings Python; no es un reemplazo inmediato y sin dependencias de `pdftotext`.

## Repositorio marcado no recomendado para esta integración: Unlimited-OCR

La verificación en Chrome confirmó que `baidu/Unlimited-OCR` procesa documentos extensos y PDF tras convertir páginas a imágenes, pero su inferencia documentada usa GPU NVIDIA, CUDA, PyTorch, Transformers y `trust_remote_code=True`; las rutas de despliegue también proponen vLLM o SGLang. Aunque es un proyecto prometedor para máxima capacidad de parsing, su coste de cómputo, modelo y superficie de confianza no encaja con un CLI local, gratuito y reproducible basado en herramientas del sistema. Se descarta para DOF Diff Lab.
