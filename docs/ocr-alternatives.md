# Alternativas OCR locales y gratuitas

El objetivo es habilitar la comparación de PDFs escaneados sin enviar documentos a terceros, preservando la distinción entre texto nativo y texto reconocido.

| Alternativa | Verificación en Chrome | Ventaja principal | Coste técnico previsto |
|---|---|---|---|
| OCRmyPDF + Tesseract | La documentación oficial indica que añade una capa OCR de texto buscable a PDFs escaneados y ofrece instalación de idiomas adicionales.[1] | Encaja directamente con el extractor existente: después se usa `pdftotext` como ya ocurre con los PDFs nativos. | Dependencias del sistema, pero sin framework Python ni modelos grandes. |
| PaddleOCR / PP-Structure | El repositorio oficial declara reconocimiento de documentos y tablas con salida estructurada, más de 100 idiomas y ejecución local.[2] | Mejor candidato si el objetivo es reconstruir tablas y celdas. | Dependencias y modelos considerables; la integración ya no es una extensión pequeña del CLI. |

La comparación no debe asumir que una mejor extracción de texto equivale a una interpretación fiable de fracciones o cuotas. OCR sirve para hacer revisable el contenido visual, no para determinar efectos normativos.

## Referencias

[1]: https://ocrmypdf.readthedocs.io/en/latest/ "OCRmyPDF documentation"
[2]: https://github.com/PaddlePaddle/PaddleOCR "PaddleOCR"

## Configuración local verificada para español

OCRmyPDF usa los paquetes de idioma de Tesseract; la documentación identifica español como `spa` y muestra el uso de `ocrmypdf -l spa`.[3] Su recetario también documenta una capa OCR local, corrección de rotación y limpieza de inclinación; estas opciones deben probarse sobre una copia de trabajo, no sobrescribir el PDF de evidencia.[4]

El punto de partida de coste cero es por tanto: instalar OCRmyPDF, Tesseract y el paquete `spa`; producir un PDF OCR derivado con una ruta nueva; extraer texto de ese derivado mediante el `pdftotext` ya usado por el proyecto; y registrar en el manifiesto que el contenido fue OCR. Esta cadena evita servicios de pago y mantiene el original inalterado.

[3]: https://ocrmypdf.readthedocs.io/en/latest/languages.html "OCRmyPDF — Installing additional language packs"
[4]: https://ocrmypdf.readthedocs.io/en/latest/cookbook.html "OCRmyPDF Cookbook"

## Madurez y licencia verificadas

La consulta de GitHub confirmó que OCRmyPDF tiene licencia MPL-2.0, aproximadamente 34 mil estrellas y actividad reciente; PaddleOCR tiene licencia Apache-2.0, aproximadamente 88 mil estrellas y actividad reciente. Ambas son alternativas maduras, pero su madurez no elimina la diferencia de coste operacional: OCRmyPDF conserva una cadena de PDF a texto ya existente, mientras que PaddleOCR añade un ecosistema de modelos y salidas estructuradas.

## Comparación para decretos escaneados

| Criterio | OCRmyPDF + Tesseract `spa` | PaddleOCR / PP-Structure |
|---|---|---|
| Coste monetario y privacidad | Sin coste de licencia ni API; procesamiento local. | Sin coste de licencia ni API; procesamiento local. |
| Integración con DOF Diff Lab | Directa: crea un PDF con capa de texto y reutiliza `pdftotext`. | Indirecta: la salida estructurada exige definir un adaptador y un formato de comparación nuevo. |
| Texto impreso español | Ruta estable y específica de idioma; debe evaluarse sobre documentos reales. | Puede reconocer múltiples idiomas, pero su ventaja no se ha medido aún sobre decretos del usuario. |
| Tablas | Conserva texto legible, pero no garantiza reconstruir columnas o filas. | Diseñado para estructura de tablas y celdas, con potencial mayor para ese caso. |
| Recursos y mantenimiento | Dependencias de sistema manejables. | Modelos y dependencias más pesados; más superficie de fallos y actualizaciones. |
| Riesgo de una falsa sensación de precisión | Bajo si el manifiesto marca OCR y se revisan códigos críticos. | Alto si se confunde JSON/Markdown estructurado con una transcripción normativamente exacta. |

No existe una respuesta honesta de “mejor OCR” sin una muestra de PDF escaneado representativa. La decisión óptima sin gastar es escalonada: usar OCRmyPDF como primer motor local y medible; mantener PaddleOCR como segunda ruta solo cuando una muestra real demuestre que los errores de estructura de tabla bloquean el uso previsto. Cambiar a PaddleOCR antes de esa evidencia añade coste técnico sin probar que resuelva el error relevante.

## Comparación de repositorios OCR marcados

| Repositorio marcado | PDFs escaneados | PDFs digitales y tablas | Dependencias / recursos | Ajuste a DOF Diff Lab |
|---|---|---|---|---|
| `ocrmypdf/OCRmyPDF` | Sí: incorpora una capa OCR local basada en Tesseract. | Reutiliza el extractor actual después del OCR; no pretende reconstruir tablas semánticas. | Herramientas locales y paquete `spa`; sin modelos GPU. | **Mejor encaje.** Mantiene el contrato de PDF → texto → diff y permite una integración pequeña. |
| `firecrawl/pdf-inspector` | No OCR; clasifica cuándo un PDF necesita OCR. | Sí: Markdown, lectura multicolumna y detección de tablas en PDFs con texto. | Rust/Cargo o bindings adicionales. | Complemento futuro, no sustituto: puede mejorar PDFs digitales y enrutar OCR. |
| `baidu/Unlimited-OCR` | Sí, con parsing visual avanzado. | Sí, pero su salida y flujo son de modelo de visión. | GPU NVIDIA/CUDA, PyTorch/Transformers, modelo y código remoto confiado. | No encaja: cambia el proyecto a una pila de ML pesada y menos reproducible. |

La selección correcta hoy es **OCRmyPDF**. `pdf-inspector` sería la mejor segunda inversión técnica cuando haya evidencia de que `pdftotext` no conserva suficiente orden o tablas en documentos digitales. `Unlimited-OCR` debe mantenerse fuera del flujo principal.
